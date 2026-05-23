package com.wemakecalls.call_service.controllers;

import com.wemakecalls.call_service.dto.ErrorResponse;
import com.wemakecalls.call_service.exceptions.CallAlreadyEndedException;
import com.wemakecalls.call_service.exceptions.CallNotFoundException;
import com.wemakecalls.call_service.exceptions.InvalidFeedbackException;
import com.wemakecalls.call_service.exceptions.NoAgentAvailableException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(NoAgentAvailableException.class)
    public ResponseEntity<ErrorResponse> handleNoAgent(NoAgentAvailableException ex) {
        return ResponseEntity.status(409).body(new ErrorResponse(ex.getMessage()));
    }

    @ExceptionHandler(CallNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(CallNotFoundException ex) {
        return ResponseEntity.status(404).body(new ErrorResponse(ex.getMessage()));
    }

    @ExceptionHandler(CallAlreadyEndedException.class)
    public ResponseEntity<ErrorResponse> handleAlreadyEnded(CallAlreadyEndedException ex) {
        return ResponseEntity.status(409).body(new ErrorResponse(ex.getMessage()));
    }

    @ExceptionHandler(InvalidFeedbackException.class)
    public ResponseEntity<ErrorResponse> handleInvalidFeedback(InvalidFeedbackException ex) {
        return ResponseEntity.status(400).body(new ErrorResponse(ex.getMessage()));
    }
}
