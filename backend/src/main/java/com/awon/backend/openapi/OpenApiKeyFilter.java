package com.awon.backend.openapi;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class OpenApiKeyFilter extends OncePerRequestFilter {
    private final OpenApiKeyService keyService;
    private final OpenApiUsageLogRepository usage;
    private final Map<Long,Window> windows=new ConcurrentHashMap<>();
    public OpenApiKeyFilter(OpenApiKeyService keyService,OpenApiUsageLogRepository usage){
        this.keyService=keyService; this.usage=usage;
    }
    @Override protected boolean shouldNotFilter(HttpServletRequest r){
        return !r.getRequestURI().startsWith("/open-api/");
    }
    @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,
                                               FilterChain chain) throws ServletException,IOException {
        long started=System.nanoTime();
        String raw=request.getHeader("X-API-Key");
        if(raw==null||raw.isBlank()){write(response,401,"OPEN_API_KEY_REQUIRED","X-API-Key 헤더가 필요합니다.");return;}
        var authenticated=keyService.authenticate(raw).orElse(null);
        if(authenticated==null){write(response,401,"OPEN_API_KEY_INVALID","유효하지 않거나 폐기된 API 키입니다.");return;}
        OrganizationApiKey key=authenticated.key(); Organization org=authenticated.organization();
        if(!allow(key.getId(),key.getRequestsPerMinute())){
            response.setHeader("Retry-After","60");
            write(response,429,"OPEN_API_RATE_LIMITED","API 호출 한도를 초과했습니다.");
            saveUsage(key,org,request,429,started); return;
        }
        OpenApiPrincipal principal=new OpenApiPrincipal(key.getId(),org.getId(),org.getName(),
                key.getKeyName(),key.getRequestsPerMinute());
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                principal,null,List.of(new SimpleGrantedAuthority("ROLE_OPEN_API"))));
        keyService.markUsed(key);
        try { chain.doFilter(request,response); }
        finally { saveUsage(key,org,request,response.getStatus(),started); }
    }
    private boolean allow(long keyId,int limit){
        long minute=Instant.now().getEpochSecond()/60;
        Window window=windows.computeIfAbsent(keyId,id->new Window(minute));
        synchronized(window){
            if(window.minute!=minute){window.minute=minute;window.count=0;}
            return ++window.count<=limit;
        }
    }
    private void saveUsage(OrganizationApiKey key,Organization org,HttpServletRequest req,int status,long started){
        int ms=(int)Math.min(Integer.MAX_VALUE,(System.nanoTime()-started)/1_000_000);
        try{usage.save(new OpenApiUsageLog(key.getId(),org.getId(),req.getMethod(),req.getRequestURI(),status,ms));}
        catch(RuntimeException ignored){ }
    }
    private void write(HttpServletResponse response,int status,String code,String message)throws IOException{
        response.setStatus(status);response.setCharacterEncoding("UTF-8");response.setContentType("application/json");
        response.getWriter().write("{\"error\":{\"code\":\""+code+"\",\"message\":\""+message+"\",\"detail\":{}}}");
    }
    private static final class Window{long minute;int count;Window(long minute){this.minute=minute;}}
}
