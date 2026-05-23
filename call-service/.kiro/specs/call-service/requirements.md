# Requirements Document

## Introduction

The call-service is a Spring Boot 4.0.6 (Java 17) microservice responsible for the call simulation side of WeMakeCalls. It manages agent availability, call session lifecycle (start → assign → track → end), feedback collection (hangup reasons and agent ratings), and real-time call timer updates via WebSocket/STOMP. All call data is persisted in MongoDB. The service runs on port 5000 in Docker and does not connect to PostgreSQL directly — a nightly sync job in the core-service handles that migration.

## Glossary

- **Call_Service**: The Spring Boot application that manages call sessions, agent availability, and real-time timer updates
- **Agent**: A call center operator who can be assigned to incoming calls
- **Call_Session**: A document in MongoDB representing a single call from start to completion, including duration, hangup reason, and agent rating
- **STOMP_Broker**: The WebSocket message broker using STOMP protocol that pushes real-time timer updates to the Angular frontend
- **Hangup_Reason**: One of five predefined reasons a call ended: Issue Resolved, Wrong Department, Long Wait Time, Call Dropped, Other
- **Agent_Rating**: A numeric score from 1 to 5 stars given by the caller to rate the agent
- **MongoDB**: The document database used to store call sessions and agent records
- **Angular_Frontend**: The single-page application that consumes the REST API and WebSocket timer updates

## Requirements

### Requirement 1: Agent Availability Retrieval

**User Story:** As a call simulator user, I want to see which agents are currently available, so that I know a call can be placed.

#### Acceptance Criteria

1. WHEN a GET request is made to `/agents/available`, THE Call_Service SHALL return a list of agents where `isAvailable` is true
2. THE Call_Service SHALL return each available agent with their `agentId` and `name` fields
3. WHEN no agents are available, THE Call_Service SHALL return an empty list with HTTP status 200

### Requirement 2: Call Session Initiation

**User Story:** As a call simulator user, I want to start a call and be assigned an available agent, so that the call simulation begins.

#### Acceptance Criteria

1. WHEN a POST request is made to `/calls/start`, THE Call_Service SHALL select an available agent and create a new Call_Session in MongoDB with status `active` and the current timestamp as `callStarted`
2. WHEN a call is started, THE Call_Service SHALL set the assigned agent's `isAvailable` field to false and record the `currentCallId` on the agent document
3. WHEN a call is started, THE Call_Service SHALL return the created Call_Session including `callId`, `agentId`, `agentName`, and `callStarted`
4. IF no agents are available when a call start is requested, THEN THE Call_Service SHALL return HTTP status 409 with an error message indicating no agents are available

### Requirement 3: Real-Time Call Timer via WebSocket

**User Story:** As a call simulator user, I want to see a live call timer updating every second, so that I can track how long the current call has been running.

#### Acceptance Criteria

1. WHILE a Call_Session has status `active`, THE STOMP_Broker SHALL publish a timer tick message every 1 second to the topic associated with that call
2. THE Call_Service SHALL include the elapsed duration in seconds in each timer tick message
3. WHEN a Call_Session status changes to `completed`, THE STOMP_Broker SHALL stop publishing timer tick messages for that call
4. THE Call_Service SHALL configure the WebSocket endpoint at `/ws` with STOMP protocol support and allow connections from the Angular_Frontend origin

### Requirement 4: Call Session Termination

**User Story:** As a call simulator user, I want to end an active call, so that the call duration is recorded and the agent becomes available again.

#### Acceptance Criteria

1. WHEN a POST request is made to `/calls/end/{callId}`, THE Call_Service SHALL set the Call_Session status to `completed` and record the current timestamp as `callEnded`
2. WHEN a call is ended, THE Call_Service SHALL calculate `durationSeconds` as the difference between `callEnded` and `callStarted`
3. WHEN a call is ended, THE Call_Service SHALL set the assigned agent's `isAvailable` field to true and clear the `currentCallId` on the agent document
4. IF the provided `callId` does not exist, THEN THE Call_Service SHALL return HTTP status 404 with an error message
5. IF the Call_Session is already in `completed` status, THEN THE Call_Service SHALL return HTTP status 409 indicating the call has already ended

### Requirement 5: Call Feedback Submission

**User Story:** As a call simulator user, I want to submit a hangup reason and agent rating after a call ends, so that call quality data is captured.

#### Acceptance Criteria

1. WHEN a POST request is made to `/calls/feedback/{callId}` with a valid hangup reason and agent rating, THE Call_Service SHALL update the Call_Session document with the provided `hangupReason` and `agentRating`
2. THE Call_Service SHALL accept only the following hangup reasons: "Issue Resolved", "Wrong Department", "Long Wait Time", "Call Dropped", "Other"
3. THE Call_Service SHALL accept only integer agent ratings in the range 1 to 5 inclusive
4. IF the provided hangup reason is not one of the five valid options, THEN THE Call_Service SHALL return HTTP status 400 with a validation error
5. IF the provided agent rating is outside the range 1 to 5, THEN THE Call_Service SHALL return HTTP status 400 with a validation error
6. IF the provided `callId` does not exist, THEN THE Call_Service SHALL return HTTP status 404 with an error message

### Requirement 6: Call History Retrieval

**User Story:** As a call simulator user, I want to view recent call history, so that I can review past call sessions and their outcomes.

#### Acceptance Criteria

1. WHEN a GET request is made to `/calls/history`, THE Call_Service SHALL return a list of Call_Session documents ordered by `callStarted` descending
2. THE Call_Service SHALL return each Call_Session with all fields: `callId`, `agentId`, `agentName`, `callStarted`, `callEnded`, `durationSeconds`, `hangupReason`, `agentRating`, and `status`
3. WHEN no call sessions exist, THE Call_Service SHALL return an empty list with HTTP status 200

### Requirement 7: MongoDB Data Persistence

**User Story:** As a system operator, I want all call data stored in MongoDB, so that the nightly sync job can pull completed calls into PostgreSQL.

#### Acceptance Criteria

1. THE Call_Service SHALL store Call_Session documents in a MongoDB collection named `calls` with fields: `agentId`, `agentName`, `callStarted`, `callEnded`, `durationSeconds`, `hangupReason`, `agentRating`, `status`
2. THE Call_Service SHALL store agent documents in a MongoDB collection named `agents` with fields: `agentId`, `name`, `isAvailable`, `currentCallId`
3. THE Call_Service SHALL use the `status` field with values `active` or `completed` to distinguish ongoing calls from finished calls

### Requirement 8: Agent State Consistency

**User Story:** As a system operator, I want agent availability to always reflect their actual call state, so that agents are not double-assigned.

#### Acceptance Criteria

1. WHEN an agent is assigned to a call, THE Call_Service SHALL atomically set `isAvailable` to false and `currentCallId` to the new call's identifier on the agent document
2. WHEN a call ends, THE Call_Service SHALL atomically set `isAvailable` to true and `currentCallId` to null on the agent document
3. THE Call_Service SHALL ensure that an agent with `isAvailable` set to false is not assigned to another call

### Requirement 9: Service Configuration

**User Story:** As a developer, I want the call-service to be properly configured for Docker deployment, so that it integrates with the WeMakeCalls infrastructure.

#### Acceptance Criteria

1. THE Call_Service SHALL run on port 5000
2. THE Call_Service SHALL connect to MongoDB using a configurable connection string from application configuration
3. THE Call_Service SHALL allow WebSocket connections from the Angular_Frontend origin via CORS configuration
