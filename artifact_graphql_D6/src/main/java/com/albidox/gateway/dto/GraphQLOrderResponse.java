package com.albidox.gateway.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record GraphQLOrderResponse(
        DataContainer data,
        List<GraphQLErrorDetail> errors
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record DataContainer(
            OrderNode order
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record OrderNode(
            String id,
            String status,
            BigDecimal totalAmount,
            UserNode user,
            List<LineItemNode> lineItems
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record UserNode(
            String name
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record LineItemNode(
            String id
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GraphQLErrorDetail(
            String message,
            List<Object> path,
            Map<String, Object> extensions
    ) {}
}
