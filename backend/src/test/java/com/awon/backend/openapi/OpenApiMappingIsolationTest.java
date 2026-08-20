package com.awon.backend.openapi;

import com.awon.backend.dictionary.TermNameCache;
import com.awon.backend.mapping.MapperClient;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OpenApiMappingIsolationTest {
    @Test
    void organizationAliasOverridesOnlyItsOwnMappings() {
        MapperClient mapper=mock(MapperClient.class);CurrentOpenApiClient client=mock(CurrentOpenApiClient.class);
        OrganizationDictionaryTermRepository terms=mock(OrganizationDictionaryTermRepository.class);
        TermNameCache global=mock(TermNameCache.class);
        var term=new OrganizationDictionaryTerm(1,"우리회사TN","우리회사tn","WQ-005","검수");
        ReflectionTestUtils.setField(term,"id",5L);
        when(client.principal()).thenReturn(new OpenApiPrincipal(1,1,"A","key",60));
        when(terms.findByOrganizationIdAndAliasNormalized(1L,"우리회사tn")).thenReturn(Optional.of(term));
        when(global.nameOf("WQ-005")).thenReturn("총질소");when(global.typeOf("WQ-005")).thenReturn("측정항목");
        OpenApiMappingService service=new OpenApiMappingService(mapper,client,terms,global);

        Map<String,Object> result=service.mapColumns(List.of("우리회사TN")).getFirst();

        assertEquals("WQ-005",result.get("code"));
        assertEquals("organization_dictionary",result.get("source"));
        verifyNoInteractions(mapper);
        verify(terms).findByOrganizationIdAndAliasNormalized(1L,"우리회사tn");
    }
}
