package com.wemakecalls.call_service.repositories;

import com.wemakecalls.call_service.models.Agent;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface AgentRepository extends MongoRepository<Agent, String> {

    List<Agent> findByIsAvailableTrue();
}
