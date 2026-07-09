import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { api } from '../api/api'
import { fetchInteractions } from './interactionsSlice'

export const sendMessage = createAsyncThunk(
  'chat/send',
  async (message, { getState, dispatch }) => {
    const history = getState().chat.messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))
    const data = await api.chat(message, history)
    dispatch(fetchInteractions())
    return data
  }
)

const chatSlice = createSlice({
  name: 'chat',
  initialState: {
    messages: [
      {
        role: 'assistant',
        content:
          "Hi! I'm your CRM assistant. Tell me about an HCP interaction and I'll log it, e.g. \"Met Dr. Sarah Chen in Boston today, she was very interested in the new trial data.\"",
        tools: [],
      },
    ],
    status: 'idle',
  },
  reducers: {
    pushUserMessage: (state, action) => {
      state.messages.push({ role: 'user', content: action.payload, tools: [] })
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state) => {
        state.status = 'loading'
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.messages.push({
          role: 'assistant',
          content: action.payload.reply,
          tools: action.payload.tools_used || [],
        })
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.status = 'failed'
        state.messages.push({
          role: 'assistant',
          content: action.error?.message || 'Sorry, something went wrong. Please try again.',
          tools: [],
        })
      })
  },
})

export const { pushUserMessage } = chatSlice.actions
export default chatSlice.reducer
