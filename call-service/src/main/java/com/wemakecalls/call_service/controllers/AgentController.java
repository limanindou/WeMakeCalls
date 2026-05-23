package com.wemakecalls.call_service.controllers;

import com.wemakecalls.call_service.dto.AgentDTO;
import com.wemakecalls.call_service.models.Agent;
import com.wemakecalls.call_service.service.AgentService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/agents")
public class AgentController {

    private final AgentService agentService;

    public AgentController(AgentService agentService) {
        this.agentService = agentService;
    }

    @GetMapping("/available")
    public List<AgentDTO> getAvailableAgents() {
        List<Agent> agents = agentService.getAvailableAgents();
        return agents.stream()
                .map(agent -> new AgentDTO(agent.getId(), agent.getName()))
                .toList();
    }
}
