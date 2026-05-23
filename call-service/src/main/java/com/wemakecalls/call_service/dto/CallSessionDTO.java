package com.wemakecalls.call_service.dto;

import java.time.Instant;

public record CallSessionDTO(
    String callId,
    String agentId,
    String agentName,
    Instant callStarted,
    Instant callEnded,
    Long durationSeconds,
    String hangupReason,
    Integer agentRating,
    String status
) {}
