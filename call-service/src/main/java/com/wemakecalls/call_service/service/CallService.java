package com.wemakecalls.call_service.service;

import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.HangupReason;

import java.util.List;

public interface CallService {

    CallSession startCall();

    CallSession endCall(String callId);

    CallSession submitFeedback(String callId, HangupReason reason, int rating);

    List<CallSession> getCallHistory();

    List<CallSession> getActiveCalls();
}
