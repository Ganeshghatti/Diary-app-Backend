# RAG Chat System - Testing Guide

## Overview
The RAG (Retrieval-Augmented Generation) chat system allows users to chat with their diary entries. It uses:
- **Pinecone** for vector search to find relevant diary entries
- **OpenAI** (text-embedding-3-small) for creating embeddings
- **Google Gemini** (gemini-2.5-flash) for generating responses

## Endpoint
**POST** `/diary/chat`

### Request Body
```json
{
  "query": "What did I do last weekend?"
}
```

### Response
Streams Server-Sent Events (SSE) with the following structure:
- `type: 'start'` - Initial metadata including number of matches found
- `type: 'chunk'` - Text chunks of the response
- `type: 'complete'` - Indicates completion
- `type: 'error'` - Error message if something went wrong

### Example Response Events
```
data: {"type": "start", "matches_found": 3}

data: {"type": "chunk", "text": "Based on your diary entries, "}

data: {"type": "chunk", "text": "last weekend you went hiking..."}

data: {"type": "complete"}
```

## Testing the RAG Chat

### Option 1: Using the Load Script (Recommended)

1. **Get your user ID** from your MongoDB users collection
2. **Load dummy entries**:
   ```bash
   python load_dummy_diaries.py <your_user_id>
   ```
   Example:
   ```bash
   python load_dummy_diaries.py 507f1f77bcf86cd799439011
   ```

3. **Test the chat endpoint** using Postman, curl, or your frontend:
   ```bash
   curl -X POST http://localhost:4000/diary/chat \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_token>" \
     -d '{"query": "What did I do last weekend?"}'
   ```

### Option 2: Using the API Directly

1. **Create diary entries** using POST `/diary` endpoint with entries from `dummy_diary_entries.json`
2. **Each entry will be automatically embedded** and stored in Pinecone
3. **Test the chat endpoint** as shown above

## Sample Queries to Test

Here are some example queries you can test with the dummy diary entries:

1. **General questions:**
   - "What did I do last weekend?"
   - "Tell me about my recent activities"
   - "What are my recent mood patterns?"

2. **Specific topics:**
   - "When did I go hiking?"
   - "Tell me about my work-related stress"
   - "What expenses did I have this week?"
   - "How many steps did I walk?"

3. **Reflection questions:**
   - "What made me happy this week?"
   - "What challenges did I face?"
   - "What did I learn recently?"

4. **Health tracking:**
   - "What's my average step count?"
   - "How's my sleep been?"
   - "What health stats did I track?"

5. **Social interactions:**
   - "Tell me about my social activities"
   - "Who did I meet recently?"

## Dummy Diary Entries

The `dummy_diary_entries.json` file contains 10 realistic diary entries covering:
- Daily activities and reflections
- Mood tracking
- Expense tracking
- Health statistics
- Work-life balance
- Social interactions
- Weekend activities
- Personal growth

### Dates Covered
- 15-01-2024 through 24-01-2024 (10 days)

## Technical Details

### RAG Flow
1. User sends a query
2. Query is embedded using OpenAI text-embedding-3-small
3. Pinecone searches for top 5 relevant diary entries (filtered by user_id)
4. Retrieved entries are formatted as context
5. Gemini generates a response based on the context and query
6. Response is streamed back to the user

### Vector Search Parameters
- **Model**: text-embedding-3-small (OpenAI)
- **Top K**: 5 most relevant entries
- **Filter**: user_id (ensures users only see their own entries)

### Response Generation
- **Model**: gemini-2.5-flash (Google)
- **Max tokens**: 1000
- **Temperature**: 0.7 (balanced creativity and coherence)

## Troubleshooting

### No matches found
- Ensure diary entries exist for the user
- Check that entries were properly embedded in Pinecone
- Verify user_id matches between MongoDB and Pinecone

### Embedding errors
- Check OPENAI_API_KEY environment variable
- Verify API key has proper permissions

### Gemini errors
- Check GEMINI_API_KEY environment variable
- Verify API key is valid and has quota

### Pinecone errors
- Check PINECONE_API_KEY environment variable
- Verify index name "diarydad" exists
- Check Pinecone index dimension matches embedding model (1536 for text-embedding-3-small)

## Frontend Integration

For frontend developers, the chat endpoint uses Server-Sent Events (SSE). Example JavaScript:

```javascript
const eventSource = new EventSource('/diary/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ query: 'Your question here' })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'start':
      console.log(`Found ${data.matches_found} relevant entries`);
      break;
    case 'chunk':
      // Append text chunk to UI
      appendToChat(data.text);
      break;
    case 'complete':
      eventSource.close();
      break;
    case 'error':
      console.error('Error:', data.error);
      break;
  }
};
```

Note: For POST requests with SSE, you may need to use a library like `fetch` with streaming or use a WebSocket connection instead.

