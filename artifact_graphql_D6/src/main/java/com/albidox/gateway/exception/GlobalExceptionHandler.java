package com.albidox.gateway.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.net.URI;
import java.time.Instant;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleResourceNotFound(ResourceNotFoundException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setTitle("Resource Not Found");
        problem.setType(URI.create("https://api.albidox.com/errors/not-found"));
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }

    @ExceptionHandler(UpstreamGraphQLException.class)
    public ProblemDetail handleUpstreamGraphQLError(UpstreamGraphQLException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_GATEWAY, ex.getMessage());
        problem.setTitle("Upstream GraphQL Error");
        problem.setType(URI.create("https://api.albidox.com/errors/upstream-graphql-error"));
        problem.setProperty("timestamp", Instant.now());
        problem.setProperty("upstreamErrors", ex.getErrors());
        return problem;
    }

    @ExceptionHandler(UpstreamTimeoutException.class)
    public ProblemDetail handleUpstreamTimeout(UpstreamTimeoutException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.GATEWAY_TIMEOUT, ex.getMessage());
        problem.setTitle("Upstream Gateway Timeout");
        problem.setType(URI.create("https://api.albidox.com/errors/gateway-timeout"));
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleGenericException(Exception ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "An internal gateway error occurred");
        problem.setTitle("Internal Server Error");
        problem.setType(URI.create("https://api.albidox.com/errors/internal-error"));
        problem.setProperty("timestamp", Instant.now());
        problem.setProperty("errorClass", ex.getClass().getSimpleName());
        return problem;
    }
}
