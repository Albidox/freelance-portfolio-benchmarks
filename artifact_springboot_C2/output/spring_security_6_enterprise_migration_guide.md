# Artifact C2-R2: Enterprise JWT & CORS Integration Guide

## 1. Spring Security 6 Migration Cheat Sheet

Migrating from Spring Boot 2 (Spring Security 5) to Spring Boot 3 (Spring Security 6) involves major architectural changes. The most significant is the complete removal of `WebSecurityConfigurerAdapter` and the deprecation of the fragile `.and()` method chaining in favor of a functional, lambda-based DSL.

### Architecture: Class Inheritance vs. Component Bean

| Feature | Legacy (Spring Security 5) | Modern (Spring Security 6) |
| :--- | :--- | :--- |
| **Base Configuration** | `extends WebSecurityConfigurerAdapter` | Register `@Bean SecurityFilterChain` |
| **DSL Style** | Method Chaining (`.and()`) | Lambda DSL (`Customizer.withDefaults()`) |
| **HTTP Authorization** | `.authorizeRequests()` | `.authorizeHttpRequests()` |
| **URL Matching** | `.antMatchers("/api/**")` | `.requestMatchers("/api/**")` |
| **Method Security** | `@EnableGlobalMethodSecurity(prePostEnabled = true)` | `@EnableMethodSecurity` |

### Code Comparison

**Before (Breaks in Spring Boot 3):**
```java
@Configuration
@EnableWebSecurity
public class SecurityConfigLegacy extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .cors().and()
            .csrf().disable()
            .sessionManagement()
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
                .and()
            .authorizeRequests()
                .antMatchers("/api/public/**").permitAll()
                .antMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
                .and()
            .httpBasic();
    }
}
```

**After (Spring Boot 3 Standard):**
```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .cors(Customizer.withDefaults())
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .httpBasic(Customizer.withDefaults());

        return http.build();
    }
}
```

---

## 2. Production Stateless JWT Filter Implementation

For commercial microservices, session state is typically offloaded to JWTs. You must insert a custom JWT validation filter *before* the standard `UsernamePasswordAuthenticationFilter`.

### `JwtAuthenticationFilter.java`
```java
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final UserDetailsService userDetailsService;

    public JwtAuthenticationFilter(JwtService jwtService, UserDetailsService userDetailsService) {
        this.jwtService = jwtService;
        this.userDetailsService = userDetailsService;
    }

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain
    ) throws ServletException, IOException {
        
        final String authHeader = request.getHeader("Authorization");
        final String jwt;
        final String username;

        // 1. Check for Bearer token presence
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        jwt = authHeader.substring(7);
        
        try {
            username = jwtService.extractUsername(jwt);
            
            // 2. If token is valid and no authentication exists in context
            if (username != null && SecurityContextHolder.getContext().getAuthentication() == null) {
                UserDetails userDetails = this.userDetailsService.loadUserByUsername(username);
                
                if (jwtService.isTokenValid(jwt, userDetails)) {
                    UsernamePasswordAuthenticationToken authToken = new UsernamePasswordAuthenticationToken(
                            userDetails,
                            null,
                            userDetails.getAuthorities()
                    );
                    authToken.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                    
                    // 3. Populate SecurityContext
                    SecurityContextHolder.getContext().setAuthentication(authToken);
                }
            }
        } catch (Exception ex) {
            // Log token expiration or signature mismatch here
            // The AuthenticationEntryPoint will handle the 401 response downstream
            logger.error("Could not set user authentication in security context", ex);
        }

        filterChain.doFilter(request, response);
    }
}
```

### Registering the Filter in `SecurityFilterChain`
You must explicitly inject this filter into the chain.

```java
@Bean
public SecurityFilterChain filterChain(HttpSecurity http, JwtAuthenticationFilter jwtAuthFilter) throws Exception {
    http
        // ... (cors, csrf, session management)
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/auth/**").permitAll()
            .anyRequest().authenticated()
        )
        // Insert JWT filter before the standard username/password filter
        .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class)
        // Handle unauthorized requests cleanly (avoids default 403 when 401 is appropriate)
        .exceptionHandling(ex -> ex
            .authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED))
        );

    return http.build();
}
```

---

## 3. Production CORS Configuration Bean

A common mistake when migrating to Spring Security 6 is relying on `@CrossOrigin` annotations on controllers. When a browser sends an `OPTIONS` preflight request without a JWT token, the Spring Security Filter Chain will intercept and block it *before* it reaches the controller, resulting in a CORS error on the frontend.

To resolve this, define a centralized `CorsConfigurationSource` bean and attach it to the `HttpSecurity` DSL. Avoid `allowedOrigins("*")` with `allowCredentials(true)` as it poses severe security vulnerabilities.

### `CorsConfigurationSource` Bean
```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import java.util.Arrays;
import java.util.List;

@Configuration
public class CorsConfig {

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        
        // 1. Specify exact origins (Never use "*" with credentials)
        configuration.setAllowedOrigins(List.of(
            "https://app.production-domain.com",
            "http://localhost:3000" // For local React/Next.js dev
        ));
        
        // 2. Allow specific methods
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        
        // 3. Allow standard and custom headers
        configuration.setAllowedHeaders(Arrays.asList(
            "Authorization", 
            "Content-Type", 
            "X-Requested-With", 
            "Accept", 
            "Origin", 
            "Access-Control-Request-Method", 
            "Access-Control-Request-Headers"
        ));
        
        // 4. Expose headers to the frontend (e.g., for pagination or rate-limiting data)
        configuration.setExposedHeaders(List.of("X-Total-Count"));
        
        // 5. Allow credentials (cookies, authorization headers)
        configuration.setAllowCredentials(true);
        
        // 6. Cache preflight responses for 1 hour to reduce network latency
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration); // Apply to all endpoints
        return source;
    }
}
```
*Note: In `SecurityFilterChain`, ensure you call `.cors(Customizer.withDefaults())` so Spring Security picks up this bean automatically by type.*

---

## 4. Security Checklist for Spring Boot 3 Audits

Before deploying a Spring Boot 3 / Spring Security 6 application to production, verify the following:

- [ ] **No Legacy Classes:** Ensure zero references to `WebSecurityConfigurerAdapter` exist in the codebase.
- [ ] **Lambda DSL Enforced:** Verify all `HttpSecurity` configurations utilize the `Customizer` lambda DSL; remove all instances of the deprecated `.and()` method chaining.
- [ ] **Stateless Sessions:** Confirm `.sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))` is explicitly set if using JWTs.
- [ ] **CORS Preflight Clearance:** Ensure preflight `OPTIONS` requests are not blocked by the security filter chain. Use a robust `CorsConfigurationSource` bean.
- [ ] **CSRF Protection:** Disable CSRF (`.csrf(AbstractHttpConfigurer::disable)`) **ONLY IF** you are using stateless JWTs and not relying on session cookies. If using cookies, leave CSRF enabled and configure a `CookieCsrfTokenRepository`.
- [ ] **Exception Handling:** Explicitly define an `AuthenticationEntryPoint` to return `401 Unauthorized` for missing/invalid credentials, preventing the framework from defaulting to `403 Forbidden` or redirecting to a login page.
- [ ] **Method Security Validation:** Ensure `@EnableGlobalMethodSecurity` is replaced with `@EnableMethodSecurity`. Verify that your `@PreAuthorize` and `@PostAuthorize` annotations operate correctly under the new framework.
- [ ] **Filter Ordering:** If injecting custom filters (like JWT validation), confirm they are added at the correct position in the filter chain (e.g., `addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class)`).
- [ ] **Password Encoding:** Verify that a strong `PasswordEncoder` (like `BCryptPasswordEncoder` or `Argon2PasswordEncoder`) is defined as a Bean and actively utilized by your `AuthenticationManager`.
