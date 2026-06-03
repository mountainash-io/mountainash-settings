# Concept List for Mountainash Settings

Total concepts: 110

## Foundation Concepts (1-12)

1. Pydantic BaseModel
2. Pydantic BaseSettings
3. Field Validators
4. Model Config
5. YAML File Format
6. TOML File Format
7. JSON File Format
8. Env File Format
9. Environment Variables
10. Python Decorators
11. Discriminated Unions
12. SecretStr Type

## Base Settings (13-22)

13. MountainAshBaseSettings Class
14. Settings Model Config
15. Post Init Lifecycle
16. Source Customization
17. Validate Assignment Invariant
18. Object Setattr Bypass
19. Settings Source Priority
20. Env Prefix Override
21. Config Files Parameter
22. Multi Format File Loading

## Settings Parameters (23-36)

23. SettingsParameters Class
24. Structural Fields
25. Runtime Fields
26. Custom Hash And Eq
27. Parameter Create Factory
28. Merge Framework
29. File List Union Strategy
30. Scalar Last Wins Strategy
31. Dict Deep Merge Strategy
32. FileHandler Class
33. File Extension Dispatch
34. File Categorization
35. KwargsHandler Class
36. Kwargs Normalization

## Field Templating (37-43)

37. Template Syntax
38. Field Name Placeholder
39. Template Resolution
40. Post Init Template Expansion
41. UPath Path Derivation
42. Template Priority Rules
43. Nested Template Resolution

## Secrets Resolution (44-55)

44. Secrets Registry
45. Secret Provider Protocol
46. Two Pass Resolution
47. Kwargs Pass Resolution
48. Model Tree Pass Resolution
49. Resolve References In Dict
50. Resolve References In Model Tree
51. Secret Prefix Syntax
52. Vault Provider
53. SSM Provider
54. Key Vault Provider
55. Frozen Model Rebuild On Resolve

## Connection Profiles (56-70)

56. ProfileDescriptor Class
57. Descriptor Identity
58. Provider Type Field
59. ParameterSpec Class
60. Parameter Name Convention
61. Parameter Python Type
62. Parameter Tier
63. Parameter Default Value
64. MISSING Sentinel
65. Driver Key Mapping
66. Secret Parameter Flag
67. Transform Function
68. Validator Function
69. DescriptorProfile Class
70. Dynamic Field Installation

## Profile Registry (71-79)

71. Registry Class
72. Name Keyed Store
73. Decorator Registration
74. Registry Decorator Factory
75. Duplicate Prevention
76. Registry Iteration
77. Registry Lookup By Name
78. Descriptor Invariants
79. Invariant Test Generator

## Auth System (80-98)

80. AuthSpec Base Class
81. Auth Kind Literal
82. Auth Discriminated Union
83. Auth Dispatch Function
84. Auth To Driver Kwargs Map
85. Default Auth Kwargs
86. NoneAuth Mode
87. PasswordAuth Mode
88. TokenAuth Mode
89. OAuth2 Client Credentials Mode
90. OAuth1 Mode
91. OAuth2 Auth Code Mode
92. IAM Auth Mode
93. Azure AD Auth Mode
94. Kerberos Auth Mode
95. Certificate Auth Mode
96. Service Account Auth Mode
97. Auth Mode Selection In Profile
98. Custom Auth Mode Extension

## Caching (99-106)

99. LRU Cache Decorator
100. Get Settings Function
101. Internal Get Settings
102. Structural Cache Key
103. Runtime Override Application
104. Model Copy For Overrides
105. SettingsManager Class
106. Named Settings Lookup

## App Settings (107-110)

107. AppSettings Class
108. App Settings Defaults
109. App Settings Templates
110. App Settings Integration
