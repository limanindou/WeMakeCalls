package com.wemakecalls.call_service.controllers;

import com.wemakecalls.call_service.dto.FeedbackRequest;
import com.wemakecalls.call_service.exceptions.CallAlreadyEndedException;
import com.wemakecalls.call_service.exceptions.CallNotFoundException;
import com.wemakecalls.call_service.exceptions.InvalidFeedbackException;
import com.wemakecalls.call_service.exceptions.NoAgentAvailableException;
import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.CallStatus;
import com.wemakecalls.call_service.models.HangupReason;
import com.wemakecalls.call_service.service.CallService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.ObjectMapper;

import java.time.Instant;
import java.util.Collections;
import java.util.List;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Unit tests for CallController.
 * Validates: Requirements 2.4, 4.4, 4.5, 5.4, 5.5, 5.6, 6.3
 */
@WebMvcTest(CallController.class)
class CallControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private CallService callService;

    // --- POST /calls/start ---

    @Test
    void startCall_success_returns200WithCallSession() throws Exception {
        CallSession session = createActiveSession("call-1", "agent-1", "Alice");

        when(callService.startCall()).thenReturn(session);

        mockMvc.perform(post("/calls/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.callId").value("call-1"))
                .andExpect(jsonPath("$.agentId").value("agent-1"))
                .andExpect(jsonPath("$.agentName").value("Alice"))
                .andExpect(jsonPath("$.status").value("ACTIVE"));
    }

    @Test
    void startCall_noAgentsAvailable_returns409() throws Exception {
        when(callService.startCall()).thenThrow(new NoAgentAvailableException("No agents are currently available"));

        mockMvc.perform(post("/calls/start"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.message").value("No agents are currently available"));
    }

    // --- POST /calls/end/{callId} ---

    @Test
    void endCall_success_returns200WithCompletedSession() throws Exception {
        CallSession session = createCompletedSession("call-1", "agent-1", "Alice", 120L);

        when(callService.endCall("call-1")).thenReturn(session);

        mockMvc.perform(post("/calls/end/call-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.callId").value("call-1"))
                .andExpect(jsonPath("$.status").value("COMPLETED"))
                .andExpect(jsonPath("$.durationSeconds").value(120));
    }

    @Test
    void endCall_callNotFound_returns404() throws Exception {
        when(callService.endCall("nonexistent")).thenThrow(new CallNotFoundException("Call not found with id: nonexistent"));

        mockMvc.perform(post("/calls/end/nonexistent"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Call not found with id: nonexistent"));
    }

    @Test
    void endCall_alreadyEnded_returns409() throws Exception {
        when(callService.endCall("call-1")).thenThrow(new CallAlreadyEndedException("Call has already ended: call-1"));

        mockMvc.perform(post("/calls/end/call-1"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.message").value("Call has already ended: call-1"));
    }

    // --- POST /calls/feedback/{callId} ---

    @Test
    void submitFeedback_success_returns200() throws Exception {
        CallSession session = createCompletedSession("call-1", "agent-1", "Alice", 120L);
        session.setHangupReason(HangupReason.ISSUE_RESOLVED);
        session.setAgentRating(5);

        when(callService.submitFeedback(eq("call-1"), eq(HangupReason.ISSUE_RESOLVED), eq(5)))
                .thenReturn(session);

        FeedbackRequest request = new FeedbackRequest("Issue Resolved", 5);

        mockMvc.perform(post("/calls/feedback/call-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.callId").value("call-1"))
                .andExpect(jsonPath("$.hangupReason").value("Issue Resolved"))
                .andExpect(jsonPath("$.agentRating").value(5));
    }

    @Test
    void submitFeedback_invalidHangupReason_returns400() throws Exception {
        FeedbackRequest request = new FeedbackRequest("Invalid Reason", 3);

        mockMvc.perform(post("/calls/feedback/call-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").exists());
    }

    @Test
    void submitFeedback_invalidRating_returns400() throws Exception {
        when(callService.submitFeedback(eq("call-1"), eq(HangupReason.ISSUE_RESOLVED), eq(0)))
                .thenThrow(new InvalidFeedbackException("Agent rating must be between 1 and 5, got: 0"));

        FeedbackRequest request = new FeedbackRequest("Issue Resolved", 0);

        mockMvc.perform(post("/calls/feedback/call-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Agent rating must be between 1 and 5, got: 0"));
    }

    @Test
    void submitFeedback_callNotFound_returns404() throws Exception {
        when(callService.submitFeedback(eq("nonexistent"), any(HangupReason.class), anyInt()))
                .thenThrow(new CallNotFoundException("Call not found with id: nonexistent"));

        FeedbackRequest request = new FeedbackRequest("Issue Resolved", 4);

        mockMvc.perform(post("/calls/feedback/nonexistent")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Call not found with id: nonexistent"));
    }

    // --- GET /calls/history ---

    @Test
    void getCallHistory_success_returnsListOfSessions() throws Exception {
        CallSession session1 = createCompletedSession("call-1", "agent-1", "Alice", 120L);
        session1.setHangupReason(HangupReason.ISSUE_RESOLVED);
        session1.setAgentRating(5);

        CallSession session2 = createCompletedSession("call-2", "agent-2", "Bob", 60L);
        session2.setHangupReason(HangupReason.WRONG_DEPARTMENT);
        session2.setAgentRating(3);

        when(callService.getCallHistory()).thenReturn(List.of(session1, session2));

        mockMvc.perform(get("/calls/history"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].callId").value("call-1"))
                .andExpect(jsonPath("$[0].agentName").value("Alice"))
                .andExpect(jsonPath("$[0].hangupReason").value("Issue Resolved"))
                .andExpect(jsonPath("$[0].agentRating").value(5))
                .andExpect(jsonPath("$[1].callId").value("call-2"))
                .andExpect(jsonPath("$[1].agentName").value("Bob"));
    }

    @Test
    void getCallHistory_empty_returnsEmptyList() throws Exception {
        when(callService.getCallHistory()).thenReturn(Collections.emptyList());

        mockMvc.perform(get("/calls/history"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
    }

    // --- Helper methods ---

    private CallSession createActiveSession(String callId, String agentId, String agentName) {
        CallSession session = new CallSession();
        session.setId(callId);
        session.setAgentId(agentId);
        session.setAgentName(agentName);
        session.setCallStarted(Instant.now());
        session.setStatus(CallStatus.ACTIVE);
        return session;
    }

    private CallSession createCompletedSession(String callId, String agentId, String agentName, Long durationSeconds) {
        CallSession session = new CallSession();
        session.setId(callId);
        session.setAgentId(agentId);
        session.setAgentName(agentName);
        session.setCallStarted(Instant.now().minusSeconds(durationSeconds));
        session.setCallEnded(Instant.now());
        session.setDurationSeconds(durationSeconds);
        session.setStatus(CallStatus.COMPLETED);
        return session;
    }
}
