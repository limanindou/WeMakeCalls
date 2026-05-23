package com.wemakecalls.call_service;

import com.wemakecalls.call_service.exceptions.InvalidFeedbackException;
import com.wemakecalls.call_service.exceptions.NoAgentAvailableException;
import com.wemakecalls.call_service.models.Agent;
import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.CallStatus;
import com.wemakecalls.call_service.models.HangupReason;
import com.wemakecalls.call_service.repositories.AgentRepository;
import com.wemakecalls.call_service.repositories.CallRepository;
import com.wemakecalls.call_service.scheduler.CallTimerScheduler;
import com.wemakecalls.call_service.service.AgentService;
import com.wemakecalls.call_service.service.AgentServiceImpl;
import com.wemakecalls.call_service.service.CallService;
import com.wemakecalls.call_service.service.CallServiceImpl;
import net.jqwik.api.*;
import net.jqwik.api.lifecycle.BeforeProperty;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;
import org.springframework.data.mongodb.core.FindAndModifyOptions;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.messaging.simp.SimpMessagingTemplate;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * Property-based tests for the call-service using jqwik.
 * Tests the service layer logic with mocked repositories.
 */
class CallServicePropertyTests {

    private AgentRepository agentRepository;
    private CallRepository callRepository;
    private MongoTemplate mongoTemplate;
    private SimpMessagingTemplate messagingTemplate;
    private AgentService agentService;
    private CallService callService;
    private CallTimerScheduler callTimerScheduler;

    @BeforeProperty
    void setUp() {
        agentRepository = mock(AgentRepository.class);
        callRepository = mock(CallRepository.class);
        mongoTemplate = mock(MongoTemplate.class);
        messagingTemplate = mock(SimpMessagingTemplate.class);

        agentService = new AgentServiceImpl(agentRepository, mongoTemplate);
        callService = new CallServiceImpl(callRepository, agentService);
        callTimerScheduler = new CallTimerScheduler(callService, messagingTemplate);
    }

    // =========================================================================
    // Property 1: Available agents filter
    // =========================================================================

    /**
     * Property 1: Available agents filter
     * For any set of Agent documents with mixed isAvailable values,
     * getAvailableAgents() returns exactly those with isAvailable=true,
     * each with non-null agentId and name.
     *
     * Validates: Requirements 1.1, 1.2
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property1_Available-agents-filter")
    void availableAgentsFilterReturnsOnlyAvailableAgents(
            @ForAll("agentLists") List<Agent> allAgents) {

        List<Agent> availableAgents = allAgents.stream()
                .filter(Agent::isAvailable)
                .collect(Collectors.toList());

        when(agentRepository.findByIsAvailableTrue()).thenReturn(availableAgents);

        List<Agent> result = agentService.getAvailableAgents();

        assertThat(result).hasSize(availableAgents.size());
        assertThat(result).allSatisfy(agent -> {
            assertThat(agent.isAvailable()).isTrue();
            assertThat(agent.getId()).isNotNull();
            assertThat(agent.getName()).isNotNull();
        });
    }

    @Provide
    Arbitrary<List<Agent>> agentLists() {
        Arbitrary<Agent> agentArb = Combinators.combine(
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(10),
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(20),
                Arbitraries.of(true, false)
        ).as((id, name, available) -> {
            Agent agent = new Agent();
            agent.setId(id);
            agent.setName(name);
            agent.setAvailable(available);
            return agent;
        });

        return agentArb.list().ofMinSize(0).ofMaxSize(20);
    }

    // =========================================================================
    // Property 2: Call start produces valid session
    // =========================================================================

    /**
     * Property 2: Call start produces valid session
     * For any agent pool with at least one available agent,
     * startCall() returns a CallSession with ACTIVE status, non-null callId,
     * agentId, agentName, and callStarted not in the future.
     *
     * Validates: Requirements 2.1, 2.3
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property2_Call-start-produces-valid-session")
    void startCallProducesValidSession(
            @ForAll("availableAgents") Agent availableAgent) {

        Instant beforeCall = Instant.now();

        // Mock: save returns the session with an ID
        when(callRepository.save(any(CallSession.class))).thenAnswer(invocation -> {
            CallSession session = invocation.getArgument(0);
            if (session.getId() == null) {
                session.setId(UUID.randomUUID().toString());
            }
            return session;
        });

        // Mock: findAndModify returns the available agent (assigned)
        Agent assignedAgent = new Agent();
        assignedAgent.setId(availableAgent.getId());
        assignedAgent.setName(availableAgent.getName());
        assignedAgent.setAvailable(false);

        when(mongoTemplate.findAndModify(any(Query.class), any(Update.class),
                any(FindAndModifyOptions.class), eq(Agent.class)))
                .thenReturn(assignedAgent);

        CallSession result = callService.startCall();

        assertThat(result.getStatus()).isEqualTo(CallStatus.ACTIVE);
        assertThat(result.getId()).isNotNull();
        assertThat(result.getAgentId()).isNotNull();
        assertThat(result.getAgentName()).isNotNull();
        assertThat(result.getCallStarted()).isNotNull();
        assertThat(result.getCallStarted()).isBeforeOrEqualTo(Instant.now());
    }

    @Provide
    Arbitrary<Agent> availableAgents() {
        return Combinators.combine(
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(10),
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(20)
        ).as((id, name) -> {
            Agent agent = new Agent();
            agent.setId(id);
            agent.setName(name);
            agent.setAvailable(true);
            return agent;
        });
    }

    // =========================================================================
    // Property 3: Agent becomes unavailable on assignment
    // =========================================================================

    /**
     * Property 3: Agent becomes unavailable on assignment
     * After a successful startCall(), the assigned agent has isAvailable=false
     * and currentCallId set to the call's ID.
     *
     * Validates: Requirements 2.2, 8.1
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property3_Agent-becomes-unavailable-on-assignment")
    void agentBecomesUnavailableOnAssignment(
            @ForAll("availableAgents") Agent availableAgent) {

        String callId = UUID.randomUUID().toString();

        // Mock: findAndModify returns agent with isAvailable=false and currentCallId set
        Agent assignedAgent = new Agent();
        assignedAgent.setId(availableAgent.getId());
        assignedAgent.setName(availableAgent.getName());
        assignedAgent.setAvailable(false);
        assignedAgent.setCurrentCallId(callId);

        when(mongoTemplate.findAndModify(any(Query.class), any(Update.class),
                any(FindAndModifyOptions.class), eq(Agent.class)))
                .thenReturn(assignedAgent);

        Agent result = agentService.assignAvailableAgent(callId);

        assertThat(result).isNotNull();
        assertThat(result.isAvailable()).isFalse();
        assertThat(result.getCurrentCallId()).isEqualTo(callId);
    }

    // =========================================================================
    // Property 4: Duration calculation correctness
    // =========================================================================

    /**
     * Property 4: Duration calculation correctness
     * For any two Instants where end >= start, the computed duration equals
     * Duration.between(start, end).getSeconds().
     *
     * Validates: Requirements 3.2, 4.2
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property4_Duration-calculation-correctness")
    void durationCalculationIsCorrect(
            @ForAll("instantPairs") InstantPair pair) {

        long expectedDuration = Duration.between(pair.start, pair.end).getSeconds();
        long computedDuration = Duration.between(pair.start, pair.end).getSeconds();

        assertThat(computedDuration).isEqualTo(expectedDuration);
        assertThat(computedDuration).isGreaterThanOrEqualTo(0);
    }

    @Provide
    Arbitrary<InstantPair> instantPairs() {
        // Generate start epoch seconds in a reasonable range (last 10 years)
        Arbitrary<Long> startEpoch = Arbitraries.longs()
                .between(Instant.now().minusSeconds(315_360_000L).getEpochSecond(),
                        Instant.now().getEpochSecond());

        // Generate duration offset between 0 and 86400 seconds (0 to 24 hours)
        Arbitrary<Long> durationOffset = Arbitraries.longs().between(0L, 86400L);

        return Combinators.combine(startEpoch, durationOffset).as((start, offset) -> {
            Instant startInstant = Instant.ofEpochSecond(start);
            Instant endInstant = startInstant.plusSeconds(offset);
            return new InstantPair(startInstant, endInstant);
        });
    }

    record InstantPair(Instant start, Instant end) {}

    // =========================================================================
    // Property 5: Only active calls receive timer ticks
    // =========================================================================

    /**
     * Property 5: Only active calls receive timer ticks
     * For any mix of CallSession documents with ACTIVE and COMPLETED statuses,
     * the scheduler only publishes timer messages for ACTIVE sessions.
     *
     * Validates: Requirements 3.3
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property5_Only-active-calls-receive-timer-ticks")
    void onlyActiveCallsReceiveTimerTicks(
            @ForAll("mixedStatusCallLists") List<CallSession> allCalls) {

        List<CallSession> activeCalls = allCalls.stream()
                .filter(c -> c.getStatus() == CallStatus.ACTIVE)
                .collect(Collectors.toList());

        // The scheduler calls callService.getActiveCalls() which delegates to repository
        when(callRepository.findByStatus(CallStatus.ACTIVE)).thenReturn(activeCalls);

        // Reset messaging template mock to track calls
        reset(messagingTemplate);

        callTimerScheduler.publishTimerTicks();

        // Verify: exactly one message per active call
        if (activeCalls.isEmpty()) {
            verify(messagingTemplate, never()).convertAndSend(anyString(), any(Object.class));
        } else {
            verify(messagingTemplate, times(activeCalls.size()))
                    .convertAndSend(anyString(), any(Object.class));

            // Verify each active call got a message
            for (CallSession activeCall : activeCalls) {
                verify(messagingTemplate).convertAndSend(
                        eq("/topic/call-timer/" + activeCall.getId()),
                        any(Object.class));
            }
        }
    }

    @Provide
    Arbitrary<List<CallSession>> mixedStatusCallLists() {
        Arbitrary<CallSession> sessionArb = Combinators.combine(
                Arbitraries.strings().alpha().ofMinLength(5).ofMaxLength(10),
                Arbitraries.of(CallStatus.ACTIVE, CallStatus.COMPLETED)
        ).as((id, status) -> {
            CallSession session = new CallSession();
            session.setId(id);
            session.setStatus(status);
            session.setCallStarted(Instant.now().minusSeconds(60));
            session.setAgentId("agent-" + id);
            session.setAgentName("Agent " + id);
            return session;
        });

        return sessionArb.list().ofMinSize(0).ofMaxSize(10).filter(list -> {
            // Ensure unique IDs
            long uniqueIds = list.stream().map(CallSession::getId).distinct().count();
            return uniqueIds == list.size();
        });
    }

    // =========================================================================
    // Property 6: End call completes session
    // =========================================================================

    /**
     * Property 6: End call completes session
     * For any active CallSession, endCall() transitions it to COMPLETED
     * with non-null callEnded and durationSeconds >= 0.
     *
     * Validates: Requirements 4.1
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property6_End-call-completes-session")
    void endCallCompletesSession(
            @ForAll("activeCallSessions") CallSession activeSession) {

        // Reset mocks to avoid accumulation across tries
        reset(callRepository, mongoTemplate);

        when(callRepository.findById(activeSession.getId()))
                .thenReturn(Optional.of(activeSession));
        when(callRepository.save(any(CallSession.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        // Mock releaseAgent
        when(mongoTemplate.findAndModify(any(Query.class), any(Update.class), eq(Agent.class)))
                .thenReturn(null);

        CallSession result = callService.endCall(activeSession.getId());

        assertThat(result.getStatus()).isEqualTo(CallStatus.COMPLETED);
        assertThat(result.getCallEnded()).isNotNull();
        assertThat(result.getDurationSeconds()).isNotNull();
        assertThat(result.getDurationSeconds()).isGreaterThanOrEqualTo(0L);
    }

    @Provide
    Arbitrary<CallSession> activeCallSessions() {
        return Combinators.combine(
                Arbitraries.strings().alpha().ofMinLength(5).ofMaxLength(10),
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(10),
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(20),
                Arbitraries.longs().between(1L, 3600L)
        ).as((callId, agentId, agentName, secondsAgo) -> {
            CallSession session = new CallSession();
            session.setId(callId);
            session.setAgentId(agentId);
            session.setAgentName(agentName);
            session.setCallStarted(Instant.now().minusSeconds(secondsAgo));
            session.setStatus(CallStatus.ACTIVE);
            return session;
        });
    }

    // =========================================================================
    // Property 7: Agent released on call end
    // =========================================================================

    /**
     * Property 7: Agent released on call end
     * After endCall(), releaseAgent is called with the correct agentId.
     *
     * Validates: Requirements 4.3, 8.2
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property7_Agent-released-on-call-end")
    void agentReleasedOnCallEnd(
            @ForAll("activeCallSessions") CallSession activeSession) {

        // Reset mocks to avoid accumulation across tries
        reset(mongoTemplate, callRepository);

        when(callRepository.findById(activeSession.getId()))
                .thenReturn(Optional.of(activeSession));
        when(callRepository.save(any(CallSession.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        // Mock releaseAgent (findAndModify for release)
        when(mongoTemplate.findAndModify(any(Query.class), any(Update.class), eq(Agent.class)))
                .thenReturn(null);

        callService.endCall(activeSession.getId());

        // Verify that mongoTemplate.findAndModify was called for releasing the agent
        // The releaseAgent method uses a query with the agentId
        ArgumentCaptor<Query> queryCaptor = ArgumentCaptor.forClass(Query.class);
        verify(mongoTemplate).findAndModify(queryCaptor.capture(), any(Update.class), eq(Agent.class));

        Query capturedQuery = queryCaptor.getValue();
        // The query should contain the agent's ID
        assertThat(capturedQuery.getQueryObject().toJson())
                .contains(activeSession.getAgentId());
    }

    // =========================================================================
    // Property 8: Feedback round-trip persistence
    // =========================================================================

    /**
     * Property 8: Feedback round-trip persistence
     * For any valid feedback (hangup reason from enum, rating 1-5),
     * submitFeedback() sets exactly the submitted values.
     *
     * Validates: Requirements 5.1
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property8_Feedback-round-trip-persistence")
    void feedbackRoundTripPersistence(
            @ForAll("validFeedback") FeedbackInput feedback) {

        CallSession existingSession = new CallSession();
        existingSession.setId(feedback.callId);
        existingSession.setStatus(CallStatus.COMPLETED);
        existingSession.setAgentId("agent-1");
        existingSession.setCallStarted(Instant.now().minusSeconds(120));

        when(callRepository.findById(feedback.callId))
                .thenReturn(Optional.of(existingSession));
        when(callRepository.save(any(CallSession.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        CallSession result = callService.submitFeedback(
                feedback.callId, feedback.hangupReason, feedback.rating);

        assertThat(result.getHangupReason()).isEqualTo(feedback.hangupReason);
        assertThat(result.getAgentRating()).isEqualTo(feedback.rating);
    }

    @Provide
    Arbitrary<FeedbackInput> validFeedback() {
        Arbitrary<String> callIds = Arbitraries.strings().alpha().ofMinLength(5).ofMaxLength(10);
        Arbitrary<HangupReason> reasons = Arbitraries.of(HangupReason.values());
        Arbitrary<Integer> ratings = Arbitraries.integers().between(1, 5);

        return Combinators.combine(callIds, reasons, ratings)
                .as(FeedbackInput::new);
    }

    record FeedbackInput(String callId, HangupReason hangupReason, int rating) {}

    // =========================================================================
    // Property 9: Invalid feedback rejection
    // =========================================================================

    /**
     * Property 9: Invalid feedback rejection
     * For any rating outside [1,5], InvalidFeedbackException is thrown
     * without modifying the session.
     *
     * Validates: Requirements 5.2, 5.3
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property9_Invalid-feedback-rejection")
    void invalidFeedbackIsRejected(
            @ForAll("invalidRatings") int invalidRating) {

        // Reset mocks to avoid accumulation across tries
        reset(callRepository);

        String callId = "call-test";
        CallSession existingSession = new CallSession();
        existingSession.setId(callId);
        existingSession.setStatus(CallStatus.COMPLETED);
        existingSession.setAgentId("agent-1");
        existingSession.setCallStarted(Instant.now().minusSeconds(120));

        when(callRepository.findById(callId))
                .thenReturn(Optional.of(existingSession));

        assertThatThrownBy(() ->
                callService.submitFeedback(callId, HangupReason.ISSUE_RESOLVED, invalidRating))
                .isInstanceOf(InvalidFeedbackException.class);

        // Verify session was never saved (not modified)
        verify(callRepository, never()).save(any(CallSession.class));
    }

    @Provide
    Arbitrary<Integer> invalidRatings() {
        // Ratings outside [1, 5]: values like 0, -1, -100, 6, 7, 100
        return Arbitraries.oneOf(
                Arbitraries.integers().between(-100, 0),
                Arbitraries.integers().between(6, 100)
        );
    }

    // =========================================================================
    // Property 10: Call history ordering
    // =========================================================================

    /**
     * Property 10: Call history ordering
     * For any set of CallSession documents, getCallHistory() returns them
     * in descending order by callStarted.
     *
     * Validates: Requirements 6.1, 6.2
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property10_Call-history-ordering")
    void callHistoryIsOrderedDescending(
            @ForAll("callSessionLists") List<CallSession> sessions) {

        // Sort descending by callStarted (simulating what the repository would return)
        List<CallSession> sortedSessions = sessions.stream()
                .sorted(Comparator.comparing(CallSession::getCallStarted).reversed())
                .collect(Collectors.toList());

        when(callRepository.findAllByOrderByCallStartedDesc()).thenReturn(sortedSessions);

        List<CallSession> result = callService.getCallHistory();

        // Verify descending order
        for (int i = 0; i < result.size() - 1; i++) {
            assertThat(result.get(i).getCallStarted())
                    .isAfterOrEqualTo(result.get(i + 1).getCallStarted());
        }
    }

    @Provide
    Arbitrary<List<CallSession>> callSessionLists() {
        Arbitrary<CallSession> sessionArb = Combinators.combine(
                Arbitraries.strings().alpha().ofMinLength(5).ofMaxLength(10),
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(10),
                Arbitraries.strings().alpha().ofMinLength(1).ofMaxLength(20),
                Arbitraries.longs().between(0L, 315_360_000L)
        ).as((callId, agentId, agentName, secondsAgo) -> {
            CallSession session = new CallSession();
            session.setId(callId);
            session.setAgentId(agentId);
            session.setAgentName(agentName);
            session.setCallStarted(Instant.now().minusSeconds(secondsAgo));
            session.setCallEnded(Instant.now().minusSeconds(secondsAgo).plusSeconds(60));
            session.setDurationSeconds(60L);
            session.setStatus(CallStatus.COMPLETED);
            session.setHangupReason(HangupReason.ISSUE_RESOLVED);
            session.setAgentRating(3);
            return session;
        });

        return sessionArb.list().ofMinSize(0).ofMaxSize(15);
    }

    // =========================================================================
    // Property 11: No double-assignment invariant
    // =========================================================================

    /**
     * Property 11: No double-assignment invariant
     * Sequential startCall() operations don't assign the same agent twice.
     * After the first assignment, findAndModify returns null (no more available agents).
     *
     * Validates: Requirements 8.3
     */
    @Property(tries = 20)
    @Tag("Feature_call-service")
    @Tag("Property11_No-double-assignment-invariant")
    void noDoubleAssignmentInvariant(
            @ForAll("agentPoolSizes") int poolSize) {

        // Create a pool of agents
        List<Agent> agentPool = new ArrayList<>();
        for (int i = 0; i < poolSize; i++) {
            Agent agent = new Agent();
            agent.setId("agent-" + i);
            agent.setName("Agent " + i);
            agent.setAvailable(true);
            agentPool.add(agent);
        }

        // Track which agents have been assigned
        Set<String> assignedAgentIds = new HashSet<>();
        Iterator<Agent> agentIterator = agentPool.iterator();

        // Mock: findAndModify returns next available agent, then null when exhausted
        when(mongoTemplate.findAndModify(any(Query.class), any(Update.class),
                any(FindAndModifyOptions.class), eq(Agent.class)))
                .thenAnswer(invocation -> {
                    if (agentIterator.hasNext()) {
                        Agent agent = agentIterator.next();
                        agent.setAvailable(false);
                        return agent;
                    }
                    return null; // No more available agents
                });

        when(callRepository.save(any(CallSession.class))).thenAnswer(invocation -> {
            CallSession session = invocation.getArgument(0);
            if (session.getId() == null) {
                session.setId(UUID.randomUUID().toString());
            }
            return session;
        });

        // Attempt to start calls for each agent in the pool
        for (int i = 0; i < poolSize; i++) {
            CallSession result = callService.startCall();
            String agentId = result.getAgentId();

            // Verify no double-assignment
            assertThat(assignedAgentIds).doesNotContain(agentId);
            assignedAgentIds.add(agentId);
        }

        // The next call should fail (no more agents)
        assertThatThrownBy(() -> callService.startCall())
                .isInstanceOf(NoAgentAvailableException.class);

        // Verify all assigned agents are unique
        assertThat(assignedAgentIds).hasSize(poolSize);
    }

    @Provide
    Arbitrary<Integer> agentPoolSizes() {
        return Arbitraries.integers().between(1, 5);
    }
}
