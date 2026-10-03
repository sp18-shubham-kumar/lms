/** Axios-shaped failures for tests that mock `api`. */
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'

export function httpError(status: number, data: unknown = {}): AxiosError {
  const response = {
    status,
    statusText: '',
    data,
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
  return new AxiosError(`HTTP ${status}`, 'ERR_BAD_REQUEST', undefined, undefined, response)
}

/** The request never got a response: server down, wrong URL, or CORS. */
export function networkError(): AxiosError {
  return new AxiosError('Network Error', 'ERR_NETWORK')
}
