package com.wemakecalls.call_service.service;

import com.wemakecalls.call_service.models.Agent;

import java.util.List;

public interface AgentService {

    List<Agent> getAvailableAgents();

    Agent assignAvailableAgent(String callId);

    void releaseAgent(String agentId);
}
