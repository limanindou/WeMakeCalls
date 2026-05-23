package com.wemakecalls.call_service.exceptions;

public class CallAlreadyEndedException extends RuntimeException {

    public CallAlreadyEndedException(String message) {
        super(message);
    }
}
