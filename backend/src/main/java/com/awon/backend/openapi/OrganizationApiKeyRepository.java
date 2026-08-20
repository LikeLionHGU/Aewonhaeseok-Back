package com.awon.backend.openapi;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;
public interface OrganizationApiKeyRepository extends JpaRepository<OrganizationApiKey,Long> {
    Optional<OrganizationApiKey> findByKeyHashAndActiveTrue(String keyHash);
    List<OrganizationApiKey> findByOrganizationIdOrderByCreatedAtDesc(Long organizationId);
    long countByOrganizationIdAndActiveTrue(Long organizationId);
}
