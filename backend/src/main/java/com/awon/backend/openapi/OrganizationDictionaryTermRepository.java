package com.awon.backend.openapi;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;
public interface OrganizationDictionaryTermRepository extends JpaRepository<OrganizationDictionaryTerm,Long> {
    Optional<OrganizationDictionaryTerm> findByOrganizationIdAndAliasNormalized(Long orgId,String normalized);
    List<OrganizationDictionaryTerm> findByOrganizationIdOrderByUpdatedAtDesc(Long orgId);
}
