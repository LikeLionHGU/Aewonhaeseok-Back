package com.awon.backend.openapi;

import com.awon.backend.common.*;
import com.awon.backend.dictionary.TermNameCache;
import com.awon.backend.mapping.MapperClient;
import com.awon.backend.mapping.dto.MapperResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.nio.file.*;
import java.text.Normalizer;
import java.util.*;

@Service
public class OpenApiMappingService {
    private static final Set<String> EXTENSIONS=Set.of("csv","xlsx","xlsm","xls");
    private final MapperClient mapper;
    private final CurrentOpenApiClient client;
    private final OrganizationDictionaryTermRepository terms;
    private final TermNameCache globalTerms;
    public OpenApiMappingService(MapperClient mapper,CurrentOpenApiClient client,
            OrganizationDictionaryTermRepository terms,TermNameCache globalTerms){
        this.mapper=mapper;this.client=client;this.terms=terms;this.globalTerms=globalTerms;
    }
    @Transactional(readOnly=true)
    public List<Map<String,Object>> mapColumns(List<String> columns){
        if(columns==null||columns.isEmpty()||columns.size()>200)
            throw new ApiException(ErrorCode.OPEN_API_COLUMNS_INVALID,
                    Map.of("columns","1~200개의 컬럼이 필요합니다."));
        List<Map<String,Object>> result=new ArrayList<>();
        for(int i=0;i<columns.size();i++)result.add(mapOne(i,columns.get(i)));
        return result;
    }
    @Transactional(readOnly=true)
    public FileMapping mapFile(MultipartFile file){
        validateFile(file);
        Path temp=null;
        try{
            temp=Files.createTempFile("awon-open-api-",".upload");
            file.transferTo(temp);
            MapperResponse mapped=mapper.map(temp,file.getOriginalFilename());
            List<Map<String,Object>> columns=new ArrayList<>();
            if(mapped.columns()!=null){
                for(int i=0;i<mapped.columns().size();i++)columns.add(mapFileColumn(i,mapped.columns().get(i)));
            }
            return new FileMapping(mapped.dictionaryVersion(),mapped.dictionaryHash(),
                    mapped.encodingDetected(),mapped.headerRow(),columns);
        }catch(IOException e){throw new ApiException(ErrorCode.FILE_STORAGE_FAILED,Map.of(),e);}
        finally{if(temp!=null)try{Files.deleteIfExists(temp);}catch(IOException ignored){}}
    }
    @Transactional
    public DictionaryTermResponse review(String raw,String standardCode,String note){
        if(!globalTerms.contains(standardCode))
            throw new ApiException(ErrorCode.STANDARD_CODE_UNKNOWN,Map.of("code",standardCode));
        long orgId=client.principal().organizationId(); String normalized=normalize(raw);
        OrganizationDictionaryTerm term=terms.findByOrganizationIdAndAliasNormalized(orgId,normalized)
                .map(existing->{existing.update(raw.trim(),standardCode,note);return existing;})
                .orElseGet(()->new OrganizationDictionaryTerm(orgId,raw.trim(),normalized,standardCode,note));
        return DictionaryTermResponse.of(terms.save(term),globalTerms.nameOf(standardCode));
    }
    @Transactional(readOnly=true)
    public List<DictionaryTermResponse> dictionary(){
        return terms.findByOrganizationIdOrderByUpdatedAtDesc(client.principal().organizationId())
                .stream().map(t->DictionaryTermResponse.of(t,globalTerms.nameOf(t.getStandardCode()))).toList();
    }
    private Map<String,Object> mapOne(int index,String raw){
        if(raw==null||raw.isBlank())throw new ApiException(ErrorCode.VERDICT_REQUIRED,Map.of("index",index));
        var orgTerm=find(raw);
        if(orgTerm.isPresent())return organizationResult(index,raw,orgTerm.get());
        Map<String,Object> result=new LinkedHashMap<>(mapper.mapColumn(raw));
        result.put("column_index",index);result.put("source","global_dictionary");return result;
    }
    private Map<String,Object> mapFileColumn(int index,MapperResponse.Col c){
        var orgTerm=find(c.raw());
        if(orgTerm.isPresent())return organizationResult(c.columnIndex()==null?index:c.columnIndex(),c.raw(),orgTerm.get());
        Map<String,Object> r=new LinkedHashMap<>();
        r.put("column_index",c.columnIndex());r.put("raw",c.raw());r.put("normalized",c.normalized());
        r.put("status",c.status());r.put("via",c.via());r.put("code",c.code());
        r.put("candidate_code",c.candidateCode());r.put("site",c.site());r.put("output_column",c.outputColumn());
        r.put("matched_variant",c.matchedVariant());r.put("score",c.score());r.put("dict_type",c.dictType());
        r.put("value_summary",c.valueSummary());r.put("source","global_dictionary");
        r.values().removeIf(Objects::isNull);return r;
    }
    private Map<String,Object> organizationResult(int index,String raw,OrganizationDictionaryTerm term){
        Map<String,Object> r=new LinkedHashMap<>();r.put("column_index",index);r.put("raw",raw);
        r.put("normalized",normalize(raw));r.put("status","organization_exact");r.put("code",term.getStandardCode());
        r.put("standard_name",globalTerms.nameOf(term.getStandardCode()));r.put("output_column",term.getStandardCode());
        r.put("dict_type",globalTerms.typeOf(term.getStandardCode()));r.put("source","organization_dictionary");return r;
    }
    private Optional<OrganizationDictionaryTerm> find(String raw){
        return terms.findByOrganizationIdAndAliasNormalized(client.principal().organizationId(),normalize(raw));
    }
    static String normalize(String value){
        if(value==null)return "";
        return Normalizer.normalize(value,Normalizer.Form.NFKC).toLowerCase(Locale.ROOT)
                .replaceAll("[\\s_\\-./()\\[\\]{}]+","");
    }
    private void validateFile(MultipartFile file){
        if(file==null||file.isEmpty())throw new ApiException(ErrorCode.FILE_EMPTY);
        String name=String.valueOf(file.getOriginalFilename());int dot=name.lastIndexOf('.');
        String ext=dot<0?"":name.substring(dot+1).toLowerCase(Locale.ROOT);
        if(!EXTENSIONS.contains(ext))throw new ApiException(ErrorCode.FILE_FORMAT_UNSUPPORTED,Map.of("given",ext));
    }
    public record FileMapping(String dictionaryVersion,String dictionaryHash,String encodingDetected,
                              Integer headerRow,List<Map<String,Object>> columns){}
    public record DictionaryTermResponse(long id,String raw,String normalized,String standardCode,
                                         String standardName,String note,java.time.OffsetDateTime updatedAt){
        static DictionaryTermResponse of(OrganizationDictionaryTerm t,String name){return new DictionaryTermResponse(
                t.getId(),t.getAliasRaw(),t.getAliasNormalized(),t.getStandardCode(),name,t.getNote(),t.getUpdatedAt());}
    }
}
