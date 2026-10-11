package com.albidox.gateway.exception;

import com.albidox.gateway.dto.GraphQLOrderResponse.GraphQLErrorDetail;
import java.util.List;

public class UpstreamGraphQLException extends RuntimeException {
    private final List<GraphQLErrorDetail> errors;

    public UpstreamGraphQLException(String message, List<GraphQLErrorDetail> errors) {
        super(message);
        this.errors = errors != null ? errors : List.of();
    }

    public List<GraphQLErrorDetail> getErrors() {
        return errors;
    }
}
