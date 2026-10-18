/**
 * Client service for profitability analysis and inventory channel allocation.
 */

import { apiRequest } from '@/services/apiClient'

export interface ChannelProfitOut {
  platform: string
  selling_price: number
  cost_price: number
  expected_demand: number
  referral_fee: number
  closing_fee: number
  logistics_fee: number
  payment_fee: number
  total_fee_per_unit: number
  net_profit_per_unit: number
  margin_pct: number
  roi_pct: number
  total_revenue: number
  total_cogs: number
  total_profit: number
  break_even_units: number
  min_selling_price_for_target: number
  fee_assumptions: Record<string, number>
}

export interface ScenarioOut {
  name: string
  demand_multiplier: number
  price_delta_pct: number
  projected_units: number
  projected_revenue: number
  projected_profit: number
  projected_margin_pct: number
}

export interface ProfitabilityResponse {
  cost_price: number
  desired_margin_pct: number
  channels: ChannelProfitOut[]
  best_channel_by_profit: string
  best_channel_by_margin: string
  scenarios_for_recommended: ScenarioOut[]
  fee_transparency_note: string
}

export interface ProfitabilityRequest {
  cost_price: number
  selling_price?: number | null
  available_inventory?: number
  desired_margin_pct?: number
  fixed_overhead?: number
  platforms?: string[]
  fee_overrides?: Record<string, Record<string, number>> | null
  product_id?: number | null
}

export interface CandidateInput {
  platform: string
  selling_price: number
  cost_price: number
  expected_demand?: number
  min_order_qty?: number
}

export interface ChannelAllocationOut {
  platform: string
  allocated_units: number
  share_pct: number
  expected_revenue: number
  expected_profit: number
  unit_margin_pct: number
  rationale: string
}

export interface OptimizationResponse {
  total_inventory: number
  total_allocated: number
  unallocated_inventory: number
  total_expected_revenue: number
  total_expected_profit: number
  average_margin_pct: number
  status: string
  allocations: ChannelAllocationOut[]
  explanation: string[]
  risk_notes: string[]
}

export interface OptimizationRequest {
  total_inventory: number
  min_margin_pct?: number
  max_channel_share?: number
  product_id?: number | null
  cost_price?: number | null
  channels?: CandidateInput[] | null
}

export async function analyzeProfitability(
  token: string,
  payload: ProfitabilityRequest,
): Promise<ProfitabilityResponse> {
  return apiRequest<ProfitabilityResponse>('/profitability/analyze', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}

export async function allocateInventory(
  token: string,
  payload: OptimizationRequest,
): Promise<OptimizationResponse> {
  return apiRequest<OptimizationResponse>('/optimization/allocate', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}
