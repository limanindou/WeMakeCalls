package com.wemakecalls.call_service.service;

import com.wemakecalls.call_service.exceptions.CallAlreadyEndedException;
import com.wemakecalls.call_service.exceptions.CallNotFoundException;
import com.wemakecalls.call_service.exceptions.InvalidFeedbackException;
import com.wemakecalls.call_service.exceptions.NoAgentAvailableException;
import com.wemakecalls.call_service.models.Agent;
import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.CallStatus;
import com.wemakecalls.call_service.models.HangupReason;
import com.wemakecalls.call_service.repositories.CallRepository;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.List;

@Service
public class CallServiceImpl implements CallService {

    private final CallRepository callRepository;
    private final AgentService agentService;

    public CallServiceImpl(CallRepository callRepository, AgentService agentService) {
        this.callRepository = callRepository;
        this.agentService = agentService;
    }

    @Override
    public CallSession startCall() {
        CallSession callSession = new CallSession();
        callSession.setStatus(CallStatus.ACTIVE);
        callSession.setCallStarted(Instant.now());

        // Save first to get the generated ID for agent assignment
        callSession = callRepository.save(callSession);

        Agent agent = agentService.assignAvailableAgent(callSession.getId());
        if (agent == null) {
            // No agent available — remove the call session and throw
            callRepository.delete(callSession);
            throw new NoAgentAvailableException("No agents are currently available");
        }

        callSession.setAgentId(agent.getId());
        callSession.setAgentName(agent.getName());

        return callRepository.save(callSession);
    }

    @Override
    public CallSession endCall(String callId) {
        CallSession callSession = callRepository.findById(callId)
                .orElseThrow(() -> new CallNotFoundException("Call not found with id: " + callId));

        if (callSession.getStatus() == CallStatus.COMPLETED) {
            throw new CallAlreadyEndedException("Call has already ended: " + callId);
        }

        Instant callEnded = Instant.now();
        callSession.setStatus(CallStatus.COMPLETED);
        callSession.setCallEnded(callEnded);
        callSession.setDurationSeconds(Duration.between(callSession.getCallStarted(), callEnded).getSeconds());

        agentService.releaseAgent(callSession.getAgentId());

        return callRepository.save(callSession);
    }

    @Override
    public CallSession submitFeedback(String callId, HangupReason reason, int rating) {
        CallSession callSession = callRepository.findById(callId)
                .orElseThrow(() -> new CallNotFoundException("Call not found with id: " + callId));

        if (rating < 1 || rating > 5) {
            throw new InvalidFeedbackException("Agent rating must be between 1 and 5, got: " + rating);
        }

        callSession.setHangupReason(reason);
        callSession.setAgentRating(rating);

        return callRepository.save(callSession);
    }

    @Override
    public List<CallSession> getCallHistory() {
        return callRepository.findAllByOrderByCallStartedDesc();
    }

    @Override
    public List<CallSession> getActiveCalls() {
        return callRepository.findByStatus(CallStatus.ACTIVE);
    }
}
