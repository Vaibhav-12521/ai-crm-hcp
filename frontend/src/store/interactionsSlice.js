import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { api } from '../api/api'

export const fetchInteractions = createAsyncThunk('interactions/fetch', () =>
  api.listInteractions()
)

export const createInteraction = createAsyncThunk('interactions/create', (payload) =>
  api.createInteraction(payload)
)

export const editInteraction = createAsyncThunk('interactions/edit', ({ id, payload }) =>
  api.updateInteraction(id, payload)
)

const interactionsSlice = createSlice({
  name: 'interactions',
  initialState: {
    items: [],
    status: 'idle',
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchInteractions.pending, (state) => {
        state.status = 'loading'
      })
      .addCase(fetchInteractions.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.items = action.payload
      })
      .addCase(fetchInteractions.rejected, (state, action) => {
        state.status = 'failed'
        state.error = action.error.message
      })
      .addCase(createInteraction.fulfilled, (state, action) => {
        state.items.unshift(action.payload)
      })
      .addCase(editInteraction.fulfilled, (state, action) => {
        const idx = state.items.findIndex((i) => i.id === action.payload.id)
        if (idx !== -1) state.items[idx] = action.payload
      })
  },
})

export default interactionsSlice.reducer
