import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

export const api = {
  listHcps: () => client.get('/hcps').then((r) => r.data),
  listInteractions: () => client.get('/interactions').then((r) => r.data),
  createInteraction: (payload) => client.post('/interactions', payload).then((r) => r.data),
  updateInteraction: (id, payload) => client.put(`/interactions/${id}`, payload).then((r) => r.data),
  chat: (message, history) => client.post('/chat', { message, history }).then((r) => r.data),
}
