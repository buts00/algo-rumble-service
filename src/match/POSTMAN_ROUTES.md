# Postman Routes for Testing the Match System

This document provides a comprehensive list of API endpoints that can be used to test the match system functionality using Postman.

## Base URL

All routes should be prefixed with your API base URL, for example: `http://localhost:8000`

## Authentication

These endpoints may require authentication. Make sure to include any necessary authentication headers in your Postman requests.

## Routes

### 1. Find a Match

Adds a user to the match queue. The user will be matched with another user with a similar rating when available.

- **URL**: `/match/find`
- **Method**: `POST`
- **Query Parameters**:
  - `user_id` (integer, required): The ID of the user looking for a match

**Example Request**:
```
POST /match/find?user_id=1
```

**Example Response**:
```json
{
  "message": "Added to match queue. You will be matched with a player of similar rating."
}
```

**Possible Error Responses**:
- 404: User not found
- 400: You already have an active or pending match

### 2. Check Queue Status

Checks if the user has been matched with another player.

- **URL**: `/match/queue/status`
- **Method**: `GET`
- **Query Parameters**:
  - `user_id` (integer, required): The ID of the user to check status for

**Example Request**:
```
GET /match/queue/status?user_id=1
```

**Example Response (when matched)**:
```json
{
  "in_match": true,
  "match_id": 123,
  "status": "pending",
  "opponent_id": 2
}
```

**Example Response (when not matched)**:
```json
{
  "in_match": false,
  "message": "Still in queue or not in queue"
}
```

### 3. Accept a Match

Accepts a match. Must be done within 15 seconds of the match being created, otherwise the match will be automatically declined.

- **URL**: `/match/accept/{match_id}`
- **Method**: `POST`
- **URL Parameters**:
  - `match_id` (integer, required): The ID of the match to accept
- **Query Parameters**:
  - `user_id` (integer, required): The ID of the user accepting the match

**Example Request**:
```
POST /match/accept/123?user_id=2
```

**Example Response**:
```json
{
  "message": "Match accepted"
}
```

**Possible Error Responses**:
- 404: Match not found
- 403: Not authorized to accept this match
- 400: Match has timed out and was automatically declined

### 4. Get Active Matches

Gets a list of active matches for a user.

- **URL**: `/match/active`
- **Method**: `GET`
- **Query Parameters**:
  - `user_id` (integer, required): The ID of the user to get active matches for

**Example Request**:
```
GET /match/active?user_id=1
```

**Example Response**:
```json
[
  {
    "id": 123,
    "player1_id": 1,
    "player2_id": 2,
    "problem_id": null,
    "status": "active",
    "winner_id": null,
    "start_time": "2023-04-17T12:34:56.789Z",
    "end_time": null
  }
]
```

## Testing Workflow

To test the match system functionality, follow these steps:

1. Use two different user IDs (e.g., 1 and 2) to simulate two players.
2. Call the **Find a Match** endpoint for both users to add them to the queue.
3. Call the **Check Queue Status** endpoint for both users repeatedly (simulating polling) to see if they've been matched.
   - In a real frontend implementation, this would be done using a setInterval or similar mechanism to poll every 1-2 seconds.
   - For testing in Postman, you can manually send the request multiple times until you see a match.
4. Once matched (when the response shows `"in_match": true`), note the `match_id` and `opponent_id` from the response.
5. Call the **Accept a Match** endpoint for the second user (player2_id) within 15 seconds using the `match_id` from the previous step.
6. Call the **Get Active Matches** endpoint for both users to verify the match is now active.

If you don't accept the match within 15 seconds, it will be automatically declined, and you'll need to start the process again.

## Frontend Implementation

### WebSockets for Real-time Notifications

The system now supports WebSockets for real-time match notifications, which is similar to how FACEIT and other modern matchmaking systems work. This approach eliminates the need for polling and provides a more efficient and responsive user experience.

#### How WebSockets Work

1. When a user logs in or enters the matchmaking page, the frontend establishes a WebSocket connection to the server.
2. When the user clicks "Find Match", the frontend calls the `/match/find` endpoint.
3. When a match is found, the server sends a notification to both players via the WebSocket connection.
4. The frontend displays a match acceptance dialog to the user.
5. If the user accepts within 15 seconds, the frontend calls the `/match/accept/{match_id}` endpoint.
6. If the user doesn't accept within 15 seconds, the match is automatically declined.

#### WebSocket Endpoint

- **URL**: `/match/ws/{user_id}`
- **Protocol**: `ws://` or `wss://` (secure)
- **Parameters**:
  - `user_id` (integer, required): The ID of the user to receive notifications for

#### Example WebSocket Implementation (JavaScript)

```javascript
// When user enters the matchmaking page
function connectToWebSocket(userId) {
  // Create WebSocket connection
  const socket = new WebSocket(`ws://localhost:8000/api/v1/match/ws/${userId}`);

  // Connection opened
  socket.addEventListener('open', (event) => {
    console.log('Connected to WebSocket');
  });

  // Listen for messages
  socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);

    if (data.in_match) {
      // Match found, show acceptance dialog
      showMatchDialog(data.match_id, data.opponent_id);
    }
  });

  // Connection closed
  socket.addEventListener('close', (event) => {
    console.log('Disconnected from WebSocket');
  });

  // Store socket reference for later use
  return socket;
}

// When user clicks "Find Match" button
async function findMatch(userId) {
  await fetch(`/match/find?user_id=${userId}`, { method: 'POST' });
  // No need to poll - we'll receive a WebSocket notification when a match is found
}

// Match acceptance dialog
function showMatchDialog(matchId, opponentId) {
  // Display dialog with 15-second countdown
  // If user clicks "Accept", call acceptMatch(matchId)
  // If countdown reaches 0, show "Match declined" message
}

// Accept match
async function acceptMatch(matchId, userId) {
  await fetch(`/match/accept/${matchId}?user_id=${userId}`, { method: 'POST' });
  // Navigate to match page or update UI
}
```

### Fallback to Polling

For clients that don't support WebSockets or in case of connection issues, the system still supports the traditional polling approach:

```javascript
// Fallback polling implementation
async function pollForMatch(userId) {
  const pollInterval = setInterval(async () => {
    const response = await fetch(`/match/queue/status?user_id=${userId}`);
    const data = await response.json();

    if (data.in_match) {
      // Match found, stop polling
      clearInterval(pollInterval);

      // Show match acceptance dialog
      showMatchDialog(data.match_id, data.opponent_id);
    }
  }, 2000); // Poll every 2 seconds

  return pollInterval; // Return interval ID for later cleanup
}
```

### Other Alternatives

While WebSockets are the recommended approach for real-time notifications, there are other alternatives:

1. **Server-Sent Events (SSE)**: Similar to WebSockets but simpler, allowing the server to push updates to the client over a long-lived HTTP connection.
2. **Long Polling**: A variation of polling where the server holds the request open until a match is found or a timeout occurs.

These alternatives could be implemented in the future if needed.

## Notes

- The match system is designed so that a player can only have one active or pending match at a time.
- Matches must be accepted within 15 seconds, otherwise they are automatically declined.
- There is no explicit decline endpoint; matches are declined automatically if not accepted within the timeout period.
- Similar to FACEIT, the system now uses WebSockets for real-time match notifications, which is more efficient than polling.
- The `/match/queue/status` endpoint is still available for clients that don't support WebSockets or as a fallback.
