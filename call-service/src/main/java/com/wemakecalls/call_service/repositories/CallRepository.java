package com.wemakecalls.call_service.repositories;

import java.util.List;

import org.springframework.data.mongodb.repository.MongoRepository;

import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.CallStatus;

public interface CallRepository extends MongoRepository<CallSession, String> {

    List<CallSession> findByStatus(CallStatus status);

    List<CallSession> findAllByOrderByCallStartedDesc();

    List<CallSession> findByStatusAndSyncedToPostgresFalse(CallStatus status);
}
