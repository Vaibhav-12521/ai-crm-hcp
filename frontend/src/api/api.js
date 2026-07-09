import axios from 'axios'

const client = axios.create({ baseURL: '/api', timeout: 60000 })

client.interceptors.response.use(
  (response) => response,
  (error) => {
    let message = 'Something went wrong. Please try again.'
    if (error.code === 'ECONNABORTED') {
      message = 'The request took too long. Please try again.'
    } else if (!error.response) {
      message = 'Unable to reach the server. Please make sure the backend is running and try again.'
    } else if (error.response.status === 404) {
      message = 'That record could not be found.'
    } else if (error.response.data && typeof error.response.data.detail === 'string') {
      message = error.response.data.detail
    } else if (error.response.status === 422) {
      message = 'Please check the details you entered and try again.'
    }
    return Promise.reject(new Error(message))
  }
)

export const api = {
  listHcps: () => client.get('/hcps').then((r) => r.data),
  listInteractions: () => client.get('/interactions').then((r) => r.data),
  createInteraction: (payload) => client.post('/interactions', payload).then((r) => r.data),
  updateInteraction: (id, payload) => client.put(`/interactions/${id}`, payload).then((r) => r.data),
  chat: (message, history) => client.post('/chat', { message, history }).then((r) => r.data),
}
