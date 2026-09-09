/** Authentication shapes returned by the backend. */

export interface User {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: string
  /** Token lifetime in seconds. */
  expires_in: number
  user: User
}

export interface RegisterPayload {
  email: string
  password: string
  full_name?: string
}

export interface LoginPayload {
  email: string
  password: string
}
