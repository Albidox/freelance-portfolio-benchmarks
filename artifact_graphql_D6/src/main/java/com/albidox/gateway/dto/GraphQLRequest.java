package com.albidox.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.Map;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record GraphQLRequest(
        String query,
        Map<String, Object> variables,
        String operationName
) {
    public GraphQLRequest(String query, Map<String, Object> variables) {
        this(query, variables, null);
    }
}
