"""Stored analytics contracts: no network, inference or training required."""
from datetime import datetime, date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models import MarketplaceSnapshot, Prediction
from app.schemas.analytics import AnalyticsFilters
from app.scrapers.base import CollectorStatus
from app.models.enums import SourceType
from app.services import analytics_service as service, training_service


@pytest.fixture
def history(db_session, client, monkeypatch):
    db_session.query(MarketplaceSnapshot).delete()
    db_session.commit()
    token = client.post('/auth/register', json={'email': f'analytics-{uuid4().hex}@example.com', 'password': 'marketpulse1'}).json()
    def forbidden(*args, **kwargs):
        raise AssertionError('Analytics must not load or train a model')
    monkeypatch.setattr(training_service, 'load_pipeline', forbidden)
    monkeypatch.setattr(training_service, 'train', forbidden)
    def add(day, **kwargs):
        values = dict(platform='amazon', source_type='demo', product_name='Test Phone', brand='Acme', category='smartphones', external_id='a', currency='INR', price=100, discount_percentage=10, rating=4, review_count=10, availability='in stock', collection_timestamp=datetime(2026, 9, day, 9), collection_run_id=str(uuid4()))
        values.update(kwargs)
        row = MarketplaceSnapshot(**values)
        db_session.add(row)
        db_session.commit()
        return row
    yield SimpleNamespace(add=add, headers={'Authorization': f"Bearer {token['access_token']}"}, user_id=token['user']['id'])
    db_session.query(MarketplaceSnapshot).delete()
    db_session.query(Prediction).filter(Prediction.user_id == token['user']['id']).delete()
    db_session.commit()


def test_calculations(history, db_session):
    history.add(1)
    history.add(3, price=80, discount_percentage=20, rating=4.5, review_count=30, availability='out of stock')
    result = service.trends(db_session, AnalyticsFilters())
    item = result['series'][0]
    assert item['price']['first'] == 100
    assert item['price']['latest'] == 80
    assert item['price']['absolute_change'] == -20
    assert item['price']['percentage_change'] == -20
    assert (item['price']['average'], item['price']['min'], item['price']['max'], item['price']['direction']) == (90, 80, 100, 'falling')
    assert item['discount']['absolute_change'] == 10
    assert item['discount']['average'] == 15
    assert item['discount']['direction'] == 'rising'
    assert item['rating']['absolute_change'] == .5
    assert item['reviews']['percentage_change'] == 200
    assert item['reviews']['momentum_per_day'] == 10
    assert item['availability']['changes'] == 1
    assert item['availability']['events'][0]['to'] == 0


def test_empty_single_and_missing_latest(history, db_session):
    assert service.trends(db_session, AnalyticsFilters())['status'] == 'insufficient_data'
    history.add(1)
    item = service.trends(db_session, AnalyticsFilters())['series'][0]
    assert item['price']['direction'] is None
    assert item['price']['latest'] == 100
    history.add(2, price=None, rating=None, review_count=None, discount_percentage=None, availability=None)
    item = service.trends(db_session, AnalyticsFilters())['series'][0]
    for field in ('price', 'rating', 'reviews', 'discount'):
        assert item[field]['latest'] is None
        assert item[field]['absolute_change'] is None
    assert item['availability']['changes'] is None


def test_zero_baseline_negative_reviews_unknown_gap(history, db_session):
    history.add(1, price=0, review_count=20)
    history.add(2, price=10, review_count=15, availability=None)
    history.add(3, price=20, review_count=10, availability='out of stock')
    item = service.trends(db_session, AnalyticsFilters())['series'][0]
    assert item['price']['percentage_change'] is None
    assert item['reviews']['momentum_per_day'] == -5
    assert item['availability']['events'] == []
    assert item['availability']['changes'] is None


def test_duplicate_source_currency_listing_boundaries(history, db_session):
    history.add(1)
    history.add(1, price=90)
    history.add(2, price=80)
    history.add(2, source_type='imported')
    history.add(2, currency='USD')
    history.add(2, external_id='b')
    result = service.trends(db_session, AnalyticsFilters())
    assert result['total_series'] == 4
    assert result['provenance']['duplicates_removed'] == 1
    repeated = next(s for s in result['series'] if s['observation_count'] == 2)
    assert repeated['price']['first'] == 90
    assert service.trends(db_session, AnalyticsFilters(source_type=SourceType.IMPORTED))['provenance']['observation_count'] == 1


def test_date_filter_and_validation(history, client):
    history.add(1)
    history.add(2, collection_timestamp=datetime(2026, 9, 2, 23, 59, 59))
    history.add(3)
    response = client.get('/analytics/trends', headers=history.headers, params={'start_date':'2026-09-02', 'end_date':'2026-09-02'})
    assert response.status_code == 200
    assert response.json()['provenance']['observation_count'] == 1
    for params in ({'start_date':'2026-09-03','end_date':'2026-09-02'}, {'source_type':'fake'}, {'platform':'fake'}, {'limit':0}, {'start_date':'bad'}):
        assert client.get('/analytics/trends', headers=history.headers, params=params).status_code == 422


@pytest.mark.parametrize('route', ['trends','platform-comparison','summary','options'])
def test_authentication(client, route):
    assert client.get('/analytics/' + route).status_code == 401


def test_comparison_grouping_and_options(history, db_session, client):
    history.add(1)
    history.add(2, price=80)
    history.add(1, platform='croma', price=120)
    history.add(1, product_name='Different Phone', external_id='b', price=200)
    history.add(1, platform='flipkart', source_type='imported', price=1)
    result = service.comparison(db_session, history.user_id, AnalyticsFilters(product='Test Phone'))
    assert len(result['groups']) == 2
    group = next(g for g in result['groups'] if g['source_type']=='demo')
    assert group['status'] == 'available'
    amazon = next(p for p in group['platforms'] if p['platform']=='amazon')
    assert amazon['average_price'] == 90
    assert amazon['listing_density'] == .5
    assert amazon['opportunity'] is None
    category = service.comparison(db_session, history.user_id, AnalyticsFilters(category='smartphones'))
    group = next(g for g in category['groups'] if g['source_type']=='demo')
    assert group['grouping'] == 'category_aggregate'
    assert next(p for p in group['platforms'] if p['platform']=='amazon')['average_price'] == 145
    assert service.comparison(db_session, history.user_id, AnalyticsFilters())['status'] == 'insufficient_data'
    response = client.get('/analytics/options', headers=history.headers, params={'q':'test phone'})
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert client.get('/analytics/platform-comparison', headers=history.headers, params={'product':'Test Phone'}).status_code == 200


def test_saved_score_exact_provenance_and_owner(history, db_session):
    history.add(1)
    key = service.trends(db_session, AnalyticsFilters())['series'][0]['product_key']
    payload = {'product_key': key, 'data_provenance': {'source_types':['demo']}, 'model':{'version':'saved-v1'}, 'warning':'Experimental', 'ranking':[{'platform':'amazon','source_type':'demo','data_freshness':'2026-09-01T09:00:00+00:00','opportunity_score':42}]}
    prediction = Prediction(user_id=history.user_id, product_name='Test Phone', result_payload=payload)
    db_session.add(prediction)
    db_session.commit()
    def score(user_id):
        group = service.comparison(db_session, user_id, AnalyticsFilters(product_key=key))['groups'][0]
        return next(p for p in group['platforms'] if p['platform']=='amazon')['opportunity']
    assert score(history.user_id)['score'] == 42
    assert score(-1) is None
    history.add(2)
    assert score(history.user_id) is None


def test_summary_and_refresh_hook(history, db_session, client, monkeypatch):
    history.add(1)
    history.add(2, source_type='imported')
    db_session.add(Prediction(user_id=history.user_id, product_name='Saved'))
    db_session.commit()
    monkeypatch.setattr(service.dataset_service, 'latest_dataset', lambda: None)
    monkeypatch.setattr(service, 'all_statuses', lambda: {'amazon': CollectorStatus(platform='amazon', available=True, reason=None, access_method='Official API (Product Advertising API 5.0)'), 'croma': CollectorStatus(platform='croma', available=True, reason=None, access_method='Future supported API')})
    response = client.get('/analytics/summary', headers=history.headers)
    assert response.status_code == 200
    body = response.json()
    assert body['stored_records'] == 2
    assert body['total_predictions'] == 1
    assert body['records_by_source_type'] == {'demo':1, 'imported':1}
    assert body['latest_observation'] == '2026-09-02T09:00:00+00:00'
    assert body['latest_observation_sources'] == ['imported']
    assert body['available_live_platforms'] == ['croma']
    assert 'deprecated' in body['refresh_sources'][0]['reason']


def test_derived_discount_and_price_stability(history, db_session):
    history.add(1, discount_percentage=None, original_price=125)
    history.add(2, price=100.5, discount_percentage=None, original_price=125)
    item = service.trends(db_session, AnalyticsFilters())['series'][0]
    assert item['price']['direction'] == 'stable'
    assert item['discount']['first'] == 20
    assert item['discount']['latest'] == pytest.approx(19.6)
    assert item['points'][0]['discount_derived'] is True
