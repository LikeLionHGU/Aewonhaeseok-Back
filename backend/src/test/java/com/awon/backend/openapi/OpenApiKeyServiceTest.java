package com.awon.backend.openapi;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class OpenApiKeyServiceTest {
    @Test
    void rawKeyIsReturnedOnceButOnlyHashIsPersisted() {
        OrganizationApiKeyRepository keys=mock(OrganizationApiKeyRepository.class);
        OrganizationRepository orgs=mock(OrganizationRepository.class);
        Organization org=new Organization("테스트기업",1);ReflectionTestUtils.setField(org,"id",9L);
        when(orgs.findById(9L)).thenReturn(Optional.of(org));
        when(keys.save(any())).thenAnswer(invocation->{OrganizationApiKey key=invocation.getArgument(0);
            ReflectionTestUtils.setField(key,"id",3L);return key;});
        OpenApiKeyService service=new OpenApiKeyService(keys,orgs);

        var issued=service.issue(9L,"운영키",60);

        assertTrue(issued.rawKey().startsWith("awon_live_"));
        assertNotEquals(issued.rawKey(),issued.entity().getKeyHash());
        assertEquals(64,issued.entity().getKeyHash().length());
        assertEquals(issued.entity().getKeyHash(),service.hash(issued.rawKey()));
    }
}
