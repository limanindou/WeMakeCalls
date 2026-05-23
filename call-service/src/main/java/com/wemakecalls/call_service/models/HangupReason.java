package com.wemakecalls.call_service.models;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum HangupReason {
    ISSUE_RESOLVED("Issue Resolved"),
    WRONG_DEPARTMENT("Wrong Department"),
    LONG_WAIT_TIME("Long Wait Time"),
    CALL_DROPPED("Call Dropped"),
    OTHER("Other");

    private final String displayName;

    HangupReason(String displayName) {
        this.displayName = displayName;
    }

    @JsonValue
    public String getDisplayName() {
        return displayName;
    }

    @JsonCreator
    public static HangupReason fromDisplayName(String displayName) {
        for (HangupReason reason : values()) {
            if (reason.displayName.equalsIgnoreCase(displayName)) {
                return reason;
            }
        }
        throw new IllegalArgumentException("Unknown HangupReason: " + displayName);
    }
}
