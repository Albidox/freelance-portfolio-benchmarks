package com.ashfaq.n1.service;

import com.ashfaq.n1.dto.UserResponseDto;
import com.ashfaq.n1.model.User;
import com.ashfaq.n1.repository.UserRepository;
import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class UserService {

    private final UserRepository userRepository;
    private final EntityManager entityManager;

    public UserService(UserRepository userRepository, EntityManager entityManager) {
        this.userRepository = userRepository;
        this.entityManager = entityManager;
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> getUsersUnoptimized() {
        // Query 1: Basic select without join fetch or entity graph
        List<User> users = entityManager.createQuery("SELECT u FROM User u", User.class).getResultList();

        // Queries 2..51: Triggering lazy collection proxy for each user
        return users.stream()
            .map(u -> new UserResponseDto(u.getId(), u.getName(), u.getEmail(), u.getOrders().size()))
            .toList();
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> getUsersOptimized() {
        // Query 1: EntityGraph hydrations (1 single joined query when @EntityGraph applied)
        List<User> users = userRepository.findAll();

        return users.stream()
            .map(u -> new UserResponseDto(u.getId(), u.getName(), u.getEmail(), u.getOrders().size()))
            .toList();
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> getUsersWithOrders() {
        // Active repository call utilized by UserController /api/users
        List<User> users = userRepository.findAll();
        return users.stream()
            .map(u -> new UserResponseDto(u.getId(), u.getName(), u.getEmail(), u.getOrders().size()))
            .toList();
    }
}
