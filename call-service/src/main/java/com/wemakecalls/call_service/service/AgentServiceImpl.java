package com.wemakecalls.call_service.service;

import com.wemakecalls.call_service.models.Agent;
import com.wemakecalls.call_service.repositories.AgentRepository;
import org.springframework.data.mongodb.core.FindAndModifyOptions;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class AgentServiceImpl implements AgentService {

    private final AgentRepository agentRepository;
    private final MongoTemplate mongoTemplate;

    public AgentServiceImpl(AgentRepository agentRepository, MongoTemplate mongoTemplate) {
        this.agentRepository = agentRepository;
        this.mongoTemplate = mongoTemplate;
    }

    @Override
    public List<Agent> getAvailableAgents() {
        return agentRepository.findByIsAvailableTrue();
    }

    @Override
    public Agent assignAvailableAgent(String callId) {
        Query query = new Query(Criteria.where("isAvailable").is(true));
        Update update = new Update()
                .set("isAvailable", false)
                .set("currentCallId", callId);
        FindAndModifyOptions options = FindAndModifyOptions.options().returnNew(true);

        return mongoTemplate.findAndModify(query, update, options, Agent.class);
    }

    @Override
    public void releaseAgent(String agentId) {
        Query query = new Query(Criteria.where("id").is(agentId));
        Update update = new Update()
                .set("isAvailable", true)
                .set("currentCallId", null);

        mongoTemplate.findAndModify(query, update, Agent.class);
    }
}
