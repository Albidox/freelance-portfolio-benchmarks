package com.ashfaq.n1.controller;

import com.ashfaq.n1.dto.UserResponseDto;
import com.ashfaq.n1.service.UserService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public List<UserResponseDto> getUsersWithOrders() {
        return userService.getUsersWithOrders();
    }
}
