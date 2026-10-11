package com.albidox.security.dto;

import java.util.List;

public record LoginResponse(
        String token,
        String tokenType,
        String username,
        List<String> roles
) {
    public LoginResponse(String token, String username, List<String> roles) {
        this(token, "Bearer", username, roles);
    }
}
