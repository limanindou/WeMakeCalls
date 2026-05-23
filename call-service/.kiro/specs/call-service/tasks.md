# Implementation Plan: call-service

## Overview

Implement the call-service Spring Boot microservice that manages agent availability, call session lifecycle, feedback collection, and real-time WebSocket timer updates. The implementation follows an incremental approach: data models and enums first, then repositories, service layer, controllers, WebSocket/scheduler, exception handling, and finally integration wiring.

## Tasks

- [x] 1. Set up project dependencies and configuration
  - [x] 1.1 Update pom.xml with WebSocket and jqwik dependencies
    - Add `spring-boot-starter-websocket` dependency
    - Add `net.jqwik:jqwik:1.9.1` test dependency
    - Remove `spring-boot-starter-data-jpa` and `spring-boot-starter-data-jpa-test` (not needed, using MongoDB only)
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 1.2 Configure application.yaml
    - Set `server.port` to 5000
    - Configure MongoDB connection string with `spring.data.mongodb.uri`
    - _Requirements: 9.1, 9.2_

- [x] 2. Create data models and enums
  - [x] 2.1 Create HangupReason enum
    - Implement enum with five values: ISSUE_RESOLVED, WRONG_DEPARTMENT, LONG_WAIT_TIME, CALL_DROPPED, OTHER
    - Add `displayName` field with `@JsonValue` and `@JsonCreator` for JSON serialization
    - Place in `com.wemakecalls.call_service.models` package
    - _Requirements: 5.2_

  - [x] 2.2 Create CallStatus enum
    - Implement enum with values: ACTIVE, COMPLETED
    - Place in `com.wemakecalls.call_service.models` package
    - _Requirements: 7.3_

  - [x] 2.3 Create CallSession document model
    - Annotate with `@Document(collection = "calls")`
    - Include fields: id, agentId, agentName, callStarted, callEnded, durationSeconds, hangupReason, agentRating, status
    - Use `Instant` for timestamps, `Long` for durationSeconds, `Integer` for agentRating
    - Place in `com.wemakecalls.call_service.models` package
    - _Requirements: 7.1_

  - [x] 2.4 Create Agent document model
    - Annotate with `@Document(collection = "agents")`
    - Include fields: id, name, isAvailable, currentCallId
    - Place in `com.wemakecalls.call_service.models` package
    - _Requirements: 7.2_

  - [x] 2.5 Create DTO records
    - Create `CallSessionDTO` record with all call session fields
    - Create `AgentDTO` record with agentId and name
    - Create `FeedbackRequest` record with hangupReason and agentRating
    - Create `TimerMessage` record with callId and elapsedSeconds
    - Create `ErrorResponse` record with message field
    - Place in `com.wemakecalls.call_service.models` package (or a `dto` sub-package)
    - _Requirements: 1.2, 2.3, 5.1, 6.2_

- [x] 3. Create repositories
  - [x] 3.1 Create CallRepository interface
    - Extend `MongoRepository<CallSession, String>`
    - Add method `findByStatus(CallStatus status)` for active call queries
    - Add method `findAllByOrderByCallStartedDesc()` for history
    - Place in `com.wemakecalls.call_service.repositories` package
    - _Requirements: 6.1, 7.1_

  - [x] 3.2 Create AgentRepository interface
    - Extend `MongoRepository<Agent, String>`
    - Add method `findByIsAvailableTrue()` for available agent queries
    - Place in `com.wemakecalls.call_service.repositories` package
    - _Requirements: 1.1, 7.2_

- [x] 4. Implement service layer
  - [x] 4.1 Implement AgentService
    - Create `AgentService` interface and `AgentServiceImpl` class
    - Implement `getAvailableAgents()` using repository query
    - Implement `assignAvailableAgent(String callId)` using MongoDB `findAndModify` for atomic update (set isAvailable=false, currentCallId=callId)
    - Implement `releaseAgent(String agentId)` using atomic update (set isAvailable=true, currentCallId=null)
    - Use `MongoTemplate` for atomic findAndModify operations
    - Place in `com.wemakecalls.call_service.service` package
    - _Requirements: 1.1, 2.2, 4.3, 8.1, 8.2, 8.3_

  - [x] 4.2 Implement CallService
    - Create `CallService` interface and `CallServiceImpl` class
    - Implement `startCall()`: call AgentService.assignAvailableAgent, create CallSession with ACTIVE status, save to repository
    - Implement `endCall(String callId)`: validate call exists and is active, set status to COMPLETED, calculate durationSeconds, release agent
    - Implement `submitFeedback(String callId, HangupReason reason, int rating)`: validate callId exists, validate rating in [1,5], update hangupReason and agentRating
    - Implement `getCallHistory()`: return all calls ordered by callStarted descending
    - Implement `getActiveCalls()`: return calls with status ACTIVE
    - Place in `com.wemakecalls.call_service.service` package
    - _Requirements: 2.1, 2.3, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 6.1_

- [x] 5. Implement exception handling
  - [x] 5.1 Create custom exception classes
    - Create `NoAgentAvailableException` (extends RuntimeException)
    - Create `CallNotFoundException` (extends RuntimeException)
    - Create `CallAlreadyEndedException` (extends RuntimeException)
    - Create `InvalidFeedbackException` (extends RuntimeException)
    - Place in `com.wemakecalls.call_service.exceptions` package (create new package)
    - _Requirements: 2.4, 4.4, 4.5, 5.4, 5.5, 5.6_

  - [x] 5.2 Create GlobalExceptionHandler
    - Annotate with `@RestControllerAdvice`
    - Map `NoAgentAvailableException` → 409
    - Map `CallNotFoundException` → 404
    - Map `CallAlreadyEndedException` → 409
    - Map `InvalidFeedbackException` → 400
    - Return `ErrorResponse` record in each handler
    - Place in `com.wemakecalls.call_service.controllers` package
    - _Requirements: 2.4, 4.4, 4.5, 5.4, 5.5, 5.6_

- [x] 6. Checkpoint - Ensure service layer compiles and unit tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement REST controllers
  - [x] 7.1 Implement AgentController
    - Annotate with `@RestController`
    - Implement `GET /agents/available` returning `List<AgentDTO>`
    - Map Agent entities to AgentDTO records
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 7.2 Implement CallController
    - Annotate with `@RestController`
    - Implement `POST /calls/start` returning `CallSessionDTO` or 409
    - Implement `POST /calls/end/{callId}` returning `CallSessionDTO`, 404, or 409
    - Implement `POST /calls/feedback/{callId}` accepting `FeedbackRequest`, returning `CallSessionDTO`, 400, or 404
    - Implement `GET /calls/history` returning `List<CallSessionDTO>`
    - Map CallSession entities to CallSessionDTO records
    - _Requirements: 2.1, 2.3, 2.4, 4.1, 4.4, 4.5, 5.1, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3_

  - [x]* 7.3 Write unit tests for controllers
    - Use MockMvc to test each endpoint's HTTP status codes and response bodies
    - Test 200 success paths, 400 validation errors, 404 not found, 409 conflict scenarios
    - _Requirements: 1.3, 2.4, 4.4, 4.5, 5.4, 5.5, 5.6, 6.3_

- [x] 8. Implement WebSocket and timer scheduler
  - [x] 8.1 Create WebSocketConfig
    - Implement `WebSocketMessageBrokerConfigurer`
    - Register STOMP endpoint at `/ws` with SockJS fallback
    - Enable simple broker on `/topic`
    - Configure allowed origins for Angular frontend CORS
    - Place in `com.wemakecalls.call_service.config` package (create new package)
    - _Requirements: 3.4, 9.3_

  - [x] 8.2 Implement CallTimerScheduler
    - Annotate class with `@Component` and enable scheduling
    - Use `@Scheduled(fixedRate = 1000)` for 1-second ticks
    - Inject `SimpMessagingTemplate` and `CallService`
    - Query active calls, calculate elapsed seconds from `callStarted` to `Instant.now()`
    - Publish `TimerMessage` to `/topic/call-timer/{callId}` for each active call
    - Place in `com.wemakecalls.call_service.scheduler` package
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 8.3 Enable scheduling in application
    - Add `@EnableScheduling` to the main application class or a configuration class
    - _Requirements: 3.1_

- [x] 9. Checkpoint - Ensure full application compiles and starts
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Write property-based tests
  - [ ]* 10.1 Write property test for available agents filter
    - **Property 1: Available agents filter**
    - Generate random lists of Agent documents with mixed isAvailable values
    - Verify getAvailableAgents() returns exactly those with isAvailable=true, each with non-null agentId and name
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 10.2 Write property test for call start produces valid session
    - **Property 2: Call start produces valid session**
    - Generate agent pools with at least one available agent
    - Verify startCall() returns CallSession with ACTIVE status, non-null callId, agentId, agentName, and callStarted not in the future
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 10.3 Write property test for agent becomes unavailable on assignment
    - **Property 3: Agent becomes unavailable on assignment**
    - Verify that after a successful startCall(), the assigned agent has isAvailable=false and currentCallId set to the call's ID
    - **Validates: Requirements 2.2, 8.1**

  - [ ]* 10.4 Write property test for duration calculation correctness
    - **Property 4: Duration calculation correctness**
    - Generate random pairs of Instants where end >= start
    - Verify computed duration equals Duration.between(start, end).getSeconds()
    - **Validates: Requirements 3.2, 4.2**

  - [ ]* 10.5 Write property test for only active calls receive timer ticks
    - **Property 5: Only active calls receive timer ticks**
    - Generate mixed-status call lists (ACTIVE and COMPLETED)
    - Verify scheduler only publishes timer messages for ACTIVE sessions
    - **Validates: Requirements 3.3**

  - [ ]* 10.6 Write property test for end call completes session
    - **Property 6: End call completes session**
    - Generate active CallSessions, call endCall()
    - Verify transition to COMPLETED with non-null callEnded and durationSeconds >= 0
    - **Validates: Requirements 4.1**

  - [ ]* 10.7 Write property test for agent released on call end
    - **Property 7: Agent released on call end**
    - Verify that after endCall(), the agent has isAvailable=true and currentCallId=null
    - **Validates: Requirements 4.3, 8.2**

  - [ ]* 10.8 Write property test for feedback round-trip persistence
    - **Property 8: Feedback round-trip persistence**
    - Generate valid feedback combinations (valid hangup reasons, ratings 1-5)
    - Verify submitFeedback() persists exactly the submitted values
    - **Validates: Requirements 5.1**

  - [ ]* 10.9 Write property test for invalid feedback rejection
    - **Property 9: Invalid feedback rejection**
    - Generate invalid hangup reason strings and ratings outside [1,5]
    - Verify rejection without modifying the CallSession
    - **Validates: Requirements 5.2, 5.3**

  - [x]* 10.10 Write property test for call history ordering
    - **Property 10: Call history ordering**
    - Generate random sets of CallSession documents with various callStarted timestamps
    - Verify getCallHistory() returns them ordered by callStarted descending with all fields present
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 10.11 Write property test for no double-assignment invariant
    - **Property 11: No double-assignment invariant**
    - Generate sequences of startCall() operations
    - Verify no agent is assigned to more than one active call simultaneously
    - **Validates: Requirements 8.3**

- [ ] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use jqwik library and validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The service uses MongoDB atomic `findAndModify` operations to prevent agent double-assignment
- WebSocket timer uses Spring's `@Scheduled` with `SimpMessagingTemplate` for STOMP publishing

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5"] },
    { "id": 2, "tasks": ["3.1", "3.2", "5.1"] },
    { "id": 3, "tasks": ["4.1", "4.2", "5.2"] },
    { "id": 4, "tasks": ["7.1", "7.2", "8.1", "8.2", "8.3"] },
    { "id": 5, "tasks": ["7.3"] },
    { "id": 6, "tasks": ["10.1", "10.2", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8", "10.9", "10.10", "10.11"] }
  ]
}
```
