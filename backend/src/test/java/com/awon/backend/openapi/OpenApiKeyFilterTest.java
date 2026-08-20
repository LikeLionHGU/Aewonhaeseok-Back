package com.awon.backend.openapi;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.*;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.*;

class OpenApiKeyFilterTest {
    @Test
    void missingKeyIsRejectedBeforeController() throws Exception {
        OpenApiKeyService keys=mock(OpenApiKeyService.class);
        OpenApiKeyFilter filter=new OpenApiKeyFilter(keys,mock(OpenApiUsageLogRepository.class));
        MockHttpServletRequest request=new MockHttpServletRequest("POST","/open-api/v1/mappings/columns");
        MockHttpServletResponse response=new MockHttpServletResponse();
        var chain=new MockFilterChain();

        filter.doFilter(request,response,chain);

        assertEquals(401,response.getStatus());
        assertTrue(response.getContentType().startsWith("application/json"));
        verifyNoInteractions(keys);
    }
}
