#pragma once

#include <cJSON.h>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <memory>

namespace JsonProtocol {

using Document = std::unique_ptr<cJSON, decltype(&cJSON_Delete)>;

inline bool digit(char c) { return c >= '0' && c <= '9'; }

inline bool validUtf8(const char* text)
{
    const auto* p = reinterpret_cast<const unsigned char*>(text);
    while (*p) {
        const unsigned char first = *p++;
        if (first < 0x80) continue;
        unsigned count = 0;
        uint32_t code = 0;
        if (first >= 0xC2 && first <= 0xDF) { count = 1; code = first & 0x1F; }
        else if (first >= 0xE0 && first <= 0xEF) { count = 2; code = first & 0x0F; }
        else if (first >= 0xF0 && first <= 0xF4) { count = 3; code = first & 0x07; }
        else return false;
        const unsigned continuationCount = count;
        while (count--) {
            if ((*p & 0xC0) != 0x80) return false;
            code = (code << 6) | (*p++ & 0x3F);
        }
        if ((continuationCount == 2 && code < 0x800) ||
            (continuationCount == 3 && code < 0x10000) ||
            (code >= 0xD800 && code <= 0xDFFF) || code > 0x10FFFF) return false;
    }
    return true;
}

inline cJSON* parse(const char* line)
{
    if (!validUtf8(line)) return nullptr;
    // cJSON accepts some non-JSON number/control forms; reject them before decoding.
    const char* p = line;
    while (*p) {
        if (*p == '"') {
            ++p;
            while (*p && *p != '"') {
                if (static_cast<unsigned char>(*p) < 0x20) return nullptr;
                if (*p == '\\') {
                    ++p;
                    // Embedded NUL cannot be represented by cJSON's C strings.
                    if (!*p || strncmp(p, "u0000", 5) == 0) return nullptr;
                    if (*p == 'u') {
                        for (unsigned i = 1; i <= 4; ++i) {
                            const char c = p[i];
                            if (!digit(c) && !(c >= 'a' && c <= 'f') && !(c >= 'A' && c <= 'F')) return nullptr;
                        }
                        p += 4;
                    }
                }
                ++p;
            }
            if (!*p) return nullptr;
            ++p;
        } else if (*p == '-' || digit(*p)) {
            if (*p == '-') ++p;
            if (*p == '0') {
                ++p;
                if (digit(*p)) return nullptr;
            } else {
                if (*p < '1' || *p > '9') return nullptr;
                while (digit(*p)) ++p;
            }
            if (*p == '.') {
                ++p;
                if (!digit(*p)) return nullptr;
                while (digit(*p)) ++p;
            }
            if (*p == 'e' || *p == 'E') {
                ++p;
                if (*p == '+' || *p == '-') ++p;
                if (!digit(*p)) return nullptr;
                while (digit(*p)) ++p;
            }
        } else {
            if (static_cast<unsigned char>(*p) < 0x20 && *p != '\t' && *p != '\r' && *p != '\n') return nullptr;
            ++p;
        }
    }
    return cJSON_ParseWithOpts(line, nullptr, true);
}

inline const char* envelope(const cJSON* request, long& id, const char*& cmd)
{
    id = 0;
    cmd = "UNKNOWN";
    if (!cJSON_IsObject(request)) return "MALFORMED_JSON";
    // The line is bounded to 160 bytes, so a simple duplicate-key check is sufficient.
    for (const cJSON* field = request->child; field; field = field->next) {
        for (const cJSON* next = field->next; next; next = next->next) {
            if (strcmp(field->string, next->string) == 0) return "DUPLICATE_FIELD";
        }
    }
    const cJSON* value = cJSON_GetObjectItemCaseSensitive(request, "id");
    if (!value) return "MISSING_ID";
    if (!cJSON_IsNumber(value) || !std::isfinite(value->valuedouble) ||
        value->valuedouble < INT32_MIN || value->valuedouble > INT32_MAX ||
        std::floor(value->valuedouble) != value->valuedouble) return "BAD_ID";
    id = static_cast<long>(value->valuedouble);

    value = cJSON_GetObjectItemCaseSensitive(request, "cmd");
    if (!value) return "MISSING_CMD";
    if (!cJSON_IsString(value) || !value->valuestring[0] || strlen(value->valuestring) > 23) return "BAD_CMD";
    // Restrict command names so echoing cmd never needs JSON escaping.
    for (const char* p = value->valuestring; *p; ++p) {
        if (!(*p >= 'A' && *p <= 'Z') && !digit(*p) && *p != '_') return "BAD_CMD";
    }
    cmd = value->valuestring;

    value = cJSON_GetObjectItemCaseSensitive(request, "v");
    if (!value) return "MISSING_VERSION";
    if (!cJSON_IsNumber(value) || !std::isfinite(value->valuedouble) ||
        std::floor(value->valuedouble) != value->valuedouble) return "BAD_VERSION";
    return value->valuedouble == 2 ? nullptr : "UNSUPPORTED_VERSION";
}

inline const char* number(const cJSON* request, const char* key, double minimum, double maximum, float& result)
{
    const cJSON* value = cJSON_GetObjectItemCaseSensitive(request, key);
    if (!value) return "MISSING_ARGUMENT";
    if (!cJSON_IsNumber(value)) return "BAD_ARGUMENT_TYPE";
    if (!std::isfinite(value->valuedouble) || value->valuedouble < minimum || value->valuedouble > maximum) return "OUT_OF_RANGE";
    result = static_cast<float>(value->valuedouble);
    return nullptr;
}

inline const char* boolean(const cJSON* request, const char* key, bool& result)
{
    const cJSON* value = cJSON_GetObjectItemCaseSensitive(request, key);
    if (!value) return "MISSING_ARGUMENT";
    if (!cJSON_IsBool(value)) return "BAD_ARGUMENT_TYPE";
    result = cJSON_IsTrue(value);
    return nullptr;
}

inline const char* string(const cJSON* request, const char* key, const char*& result)
{
    const cJSON* value = cJSON_GetObjectItemCaseSensitive(request, key);
    if (!value) return "MISSING_ARGUMENT";
    if (!cJSON_IsString(value)) return "BAD_ARGUMENT_TYPE";
    result = value->valuestring;
    return nullptr;
}

} // namespace JsonProtocol
