package com.awon.backend.openapi;

import org.springframework.context.annotation.*;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.config.Customizer;

@Configuration
public class OpenApiSecurityConfig {
    @Bean @Order(1)
    SecurityFilterChain openApiSecurity(HttpSecurity http,OpenApiKeyFilter filter)throws Exception{
        http.securityMatcher("/open-api/**")
                .csrf(c->c.disable()).cors(Customizer.withDefaults())
                .sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a->a.anyRequest().authenticated())
                .addFilterBefore(filter,UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
