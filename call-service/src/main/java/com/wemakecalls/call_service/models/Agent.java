package com.wemakecalls.call_service.models;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

@Document(collection = "agents")
public class Agent {

    @Id
    private String id;

    private String name;

    private boolean isAvailable;

    private String currentCallId;

    public Agent() {
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public boolean isAvailable() {
        return isAvailable;
    }

    public void setAvailable(boolean available) {
        isAvailable = available;
    }

    public String getCurrentCallId() {
        return currentCallId;
    }

    public void setCurrentCallId(String currentCallId) {
        this.currentCallId = currentCallId;
    }
}
