package com.wemakecalls.call_service.models;

import java.time.Instant;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

@Document(collection = "calls")
public class CallSession {

    @Id
    private String id;

    private String agentId;

    private String agentName;

    private Instant callStarted;

    private Instant callEnded;

    private Long durationSeconds;

    private HangupReason hangupReason;

    private Integer agentRating;

    private CallStatus status;

    private boolean syncedToPostgres;

    public CallSession() {
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getAgentId() {
        return agentId;
    }

    public void setAgentId(String agentId) {
        this.agentId = agentId;
    }

    public String getAgentName() {
        return agentName;
    }

    public void setAgentName(String agentName) {
        this.agentName = agentName;
    }

    public Instant getCallStarted() {
        return callStarted;
    }

    public void setCallStarted(Instant callStarted) {
        this.callStarted = callStarted;
    }

    public Instant getCallEnded() {
        return callEnded;
    }

    public void setCallEnded(Instant callEnded) {
        this.callEnded = callEnded;
    }

    public Long getDurationSeconds() {
        return durationSeconds;
    }

    public void setDurationSeconds(Long durationSeconds) {
        this.durationSeconds = durationSeconds;
    }

    public HangupReason getHangupReason() {
        return hangupReason;
    }

    public void setHangupReason(HangupReason hangupReason) {
        this.hangupReason = hangupReason;
    }

    public Integer getAgentRating() {
        return agentRating;
    }

    public void setAgentRating(Integer agentRating) {
        this.agentRating = agentRating;
    }

    public CallStatus getStatus() {
        return status;
    }

    public void setStatus(CallStatus status) {
        this.status = status;
    }

    public boolean isSyncedToPostgres() {
        return syncedToPostgres;
    }

    public void setSyncedToPostgres(boolean syncedToPostgres) {
        this.syncedToPostgres = syncedToPostgres;
    }
}
