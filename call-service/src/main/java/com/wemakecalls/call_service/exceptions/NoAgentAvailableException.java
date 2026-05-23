package com.wemakecalls.call_service.exceptions;

public class NoAgentAvailableException extends RuntimeException {

    public NoAgentAvailableException(String message) {
        super(message);
    }
}
