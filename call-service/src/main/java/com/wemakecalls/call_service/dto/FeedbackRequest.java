package com.wemakecalls.call_service.dto;

public record FeedbackRequest(
    String hangupReason,
    int agentRating
) {}
