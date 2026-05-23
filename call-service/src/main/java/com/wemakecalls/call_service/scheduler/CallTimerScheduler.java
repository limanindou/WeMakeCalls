package com.wemakecalls.call_service.scheduler;

import java.time.Duration;
import java.time.Instant;
import java.util.List;

import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.wemakecalls.call_service.dto.TimerMessage;
import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.service.CallService;

@Component
public class CallTimerScheduler {

    private final CallService callService;
    private final SimpMessagingTemplate messagingTemplate;

    public CallTimerScheduler(CallService callService, SimpMessagingTemplate messagingTemplate) {
        this.callService = callService;
        this.messagingTemplate = messagingTemplate;
    }

    @Scheduled(fixedRate = 1000)
    public void publishTimerTicks() {
        List<CallSession> activeCalls = callService.getActiveCalls();
        Instant now = Instant.now();
        for (CallSession call : activeCalls) {
            long elapsedSeconds = Duration.between(call.getCallStarted(), now).getSeconds();
            TimerMessage message = new TimerMessage(call.getId(), elapsedSeconds);
            messagingTemplate.convertAndSend("/topic/call-timer/" + call.getId(), message);
        }
    }
}
