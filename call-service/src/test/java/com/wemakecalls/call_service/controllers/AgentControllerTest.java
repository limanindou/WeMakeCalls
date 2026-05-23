package com.wemakecalls.call_service.controllers;

import com.wemakecalls.call_service.models.Agent;
import com.wemakecalls.call_service.service.AgentService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Collections;
import java.util.List;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Unit tests for AgentController.
 * Validates: Requirements 1.3
 */
@WebMvcTest(AgentController.class)
class AgentControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AgentService agentService;

    @Test
    void getAvailableAgents_returnsListOfAgents() throws Exception {
        Agent agent1 = new Agent();
        agent1.setId("agent-1");
        agent1.setName("Alice");
        agent1.setAvailable(true);

        Agent agent2 = new Agent();
        agent2.setId("agent-2");
        agent2.setName("Bob");
        agent2.setAvailable(true);

        when(agentService.getAvailableAgents()).thenReturn(List.of(agent1, agent2));

        mockMvc.perform(get("/agents/available"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].agentId").value("agent-1"))
                .andExpect(jsonPath("$[0].name").value("Alice"))
                .andExpect(jsonPath("$[1].agentId").value("agent-2"))
                .andExpect(jsonPath("$[1].name").value("Bob"));
    }

    @Test
    void getAvailableAgents_noAgentsAvailable_returnsEmptyList() throws Exception {
        when(agentService.getAvailableAgents()).thenReturn(Collections.emptyList());

        mockMvc.perform(get("/agents/available"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
    }
}
