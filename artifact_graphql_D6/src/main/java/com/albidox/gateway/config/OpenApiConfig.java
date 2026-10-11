package com.albidox.gateway.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.servers.Server;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("GraphQL to REST Gateway Adapter API")
                        .version("1.0.0")
                        .description("High-performance Spring Boot 3.4 gateway adapting complex upstream GraphQL entities into clean, predictable REST endpoints. Eliminates payload over-fetching by requesting exact DTO projection fields.")
                        .contact(new Contact()
                                .name("Ashfaq - Lead Backend Specialist")
                                .url("https://github.com/Albidox"))
                        .license(new License()
                                .name("Apache 2.0")
                                .url("https://www.apache.org/licenses/LICENSE-2.0")))
                .servers(List.of(
                        new Server().url("http://localhost:8081").description("Local Gateway Adapter Instance")
                ));
    }
}
