package com.awon.backend.standard;

import com.awon.backend.common.ApiException;
import com.awon.backend.common.ErrorCode;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.RequestParam;

import java.lang.reflect.Method;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

class StandardControllerTest {

    private final StandardController controller = new StandardController(mock(JdbcTemplate.class));

    @Test
    void limitsRequiresScaleInHttpContract() throws Exception {
        Method method = StandardController.class.getMethod(
                "limits", String.class, String.class, String.class, String.class);
        RequestParam annotation = method.getParameters()[3].getAnnotation(RequestParam.class);

        assertTrue(annotation.required());
    }

    @Test
    void limitsRejectsBlankScaleInsteadOfReturningOnlyCommonItems() {
        ApiException exception = assertThrows(ApiException.class,
                () -> controller.limits("배출허용기준", null, null, " "));

        assertEquals(ErrorCode.STANDARD_SCALE_REQUIRED, exception.errorCode());
    }
}
