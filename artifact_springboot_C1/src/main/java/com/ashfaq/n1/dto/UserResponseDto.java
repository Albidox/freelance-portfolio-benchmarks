package com.ashfaq.n1.dto;

public record UserResponseDto(
    Long id,
    String name,
    String email,
    int orderCount
) {
    public UserResponseDto(Long id, String name, int orderCount) {
        this(id, name, null, orderCount);
    }
}
