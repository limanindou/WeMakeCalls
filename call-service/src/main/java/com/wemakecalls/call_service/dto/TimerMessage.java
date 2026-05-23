package com.wemakecalls.call_service.dto;

public record TimerMessage(
    String callId,
    long elapsedSeconds
) {}
