package com.awon.backend.openapi;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.time.OffsetDateTime;
public interface OpenApiUsageLogRepository extends JpaRepository<OpenApiUsageLog,Long> {
    @Query("select count(u) from OpenApiUsageLog u where u.organizationId=:orgId and u.requestedAt>=:from")
    long countRecent(@Param("orgId") Long orgId, @Param("from") OffsetDateTime from);
}
