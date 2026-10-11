package com.ashfaq.n1.config;

import com.ashfaq.n1.model.Order;
import com.ashfaq.n1.model.User;
import com.ashfaq.n1.repository.UserRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Component
public class DataSeeder implements CommandLineRunner {

    private final UserRepository userRepository;

    public DataSeeder(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    @Transactional
    public void run(String... args) {
        if (userRepository.count() > 0) {
            return;
        }

        List<User> users = new ArrayList<>(50);
        for (int i = 1; i <= 50; i++) {
            User user = new User("User_" + i, "user" + i + "@example.com");
            for (int j = 1; j <= 5; j++) {
                Order order = new Order(
                    BigDecimal.valueOf(10.0 * j),
                    "COMPLETED",
                    user
                );
                user.addOrder(order);
            }
            users.add(user);
        }
        userRepository.saveAll(users);
    }
}
