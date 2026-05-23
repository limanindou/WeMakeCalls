package com.wemakecalls.call_service.exceptions;

public class CallNotFoundException extends RuntimeException {

    public CallNotFoundException(String message) {
        super(message);
    }
}
