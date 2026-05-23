package com.wemakecalls.call_service.controllers;

import com.wemakecalls.call_service.dto.CallSessionDTO;
import com.wemakecalls.call_service.dto.FeedbackRequest;
import com.wemakecalls.call_service.exceptions.InvalidFeedbackException;
import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.HangupReason;
import com.wemakecalls.call_service.service.CallService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/calls")
public class CallController {

    private final CallService callService;

    public CallController(CallService callService) {
        this.callService = callService;
    }

    @PostMapping("/start")
    public CallSessionDTO startCall() {
        CallSession session = callService.startCall();
        return toDTO(session);
    }

    @PostMapping("/end/{callId}")
    public CallSessionDTO endCall(@PathVariable String callId) {
        CallSession session = callService.endCall(callId);
        return toDTO(session);
    }

    @PostMapping("/feedback/{callId}")
    public CallSessionDTO submitFeedback(@PathVariable String callId, @RequestBody FeedbackRequest request) {
        HangupReason reason;
        try {
            reason = HangupReason.fromDisplayName(request.hangupReason());
        } catch (IllegalArgumentException ex) {
            throw new InvalidFeedbackException("Invalid hangup reason: " + request.hangupReason());
        }
        CallSession session = callService.submitFeedback(callId, reason, request.agentRating());
        return toDTO(session);
    }

    @GetMapping("/history")
    public List<CallSessionDTO> getCallHistory() {
        return callService.getCallHistory().stream()
                .map(this::toDTO)
                .toList();
    }

    private CallSessionDTO toDTO(CallSession session) {
        return new CallSessionDTO(
                session.getId(),
                session.getAgentId(),
                session.getAgentName(),
                session.getCallStarted(),
                session.getCallEnded(),
                session.getDurationSeconds(),
                session.getHangupReason() != null ? session.getHangupReason().getDisplayName() : null,
                session.getAgentRating(),
                session.getStatus().name()
        );
    }
}
