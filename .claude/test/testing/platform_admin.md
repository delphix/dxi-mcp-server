# Test Prompts: platform_admin

> `DCT_TOOLSET=platform_admin`

Set `DCT_TOOLSET=platform_admin` in `.mcp.json` and restart the dct MCP server. Then execute the prompts top to bottom via the dct MCP tools — Claude is the runner. Prompts are chained: IDs discovered in earlier steps carry forward to later ones.

For confirmation-flow prompts the first call returns `confirmation_required`; re-issue the same call with `confirmed=True` to execute.

---

**job_tool**
1. Search for all jobs
2. Get the details of the first job
3. Get the result of the first completed job
4. Abandon the first running job, if any exist (first call returns confirmation; confirm to proceed)
5. Get the tags for the first job
6. Add the tag monitored=true to the first job

**engine_tool**
7. Search for all registered engines
8. Get the details of the first engine
9. Register a new engine using a test engine address (first call returns confirmation; confirm to proceed)
10. Update that engine's description to "managed by platform admin"
11. Get the tags for that engine
12. Add the tag tier=production to that engine
13. Remove the tier=production tag from that engine
14. Unregister the test engine (first call returns confirmation; confirm to proceed)

**environment_tool**
15. Search for all environments
16. Get the details of the first environment
17. Create a new environment using a test host address
18. Update that environment's description to "platform admin test env"
19. Add users to that environment
20. Set the primary user for that environment
21. Update that environment's user
22. Delete that environment's user
23. Enable that environment
24. Disable that environment
25. Refresh that environment
26. List the hosts in that environment
27. List the listeners in that environment
28. Get the tags for that environment
29. Add the tag managed=true to that environment
30. Remove the managed=true tag from that environment
31. Delete that environment (first call returns confirmation; confirm to proceed)

**source_tool**
32. Search for all sources
33. Get the details of the first source
34. Update that source's configuration
35. Get the tags for that source
36. Add the tag monitored=true to that source
37. Remove the monitored=true tag from that source

**replication_tool — Replication Profile operations**
38. Search for all replication profiles
39. Get the details of the first replication profile
40. Create a new replication profile named test-pa-replication-profile
41. Update that profile's description to "platform admin test"
42. Execute that replication profile (first call returns confirmation; confirm to proceed)
43. Enable tag replication for that profile
44. Disable tag replication for that profile
45. Get the tags for that profile
46. Add the tag managed=dr to that profile
47. Remove the managed=dr tag from that profile
48. Delete that profile (first call returns confirmation; confirm to proceed)

**replication_tool — Namespace operations**
49. List all namespaces
50. Search for all namespaces
51. Get the details of the first namespace
52. Update that namespace's description
53. Failover the first namespace (first call returns confirmation; confirm to proceed)
54. Commit the failover for that namespace (first call returns confirmation; confirm to proceed)
55. Fail back that namespace (first call returns confirmation; confirm to proceed)
56. Discard that namespace (first call returns confirmation; confirm to proceed)
57. Delete that namespace (first call returns confirmation; confirm to proceed)

**replication_tool — Held Space operations**
58. Get the deletion dependencies for the first held space
59. Delete the first held space (first call returns confirmation; confirm to proceed)

**reporting_tool**
60. Search the storage savings report
61. Get the storage capacity report
62. Get the virtualization storage summary report
63. Get the VDB inventory report
64. Search the VDB inventory report filtered by engine
65. Get the dSource consumption report
66. Get the engine performance analytics report
67. Get the dataset performance analytics report
68. Get the API usage report
69. Get the audit logs summary report
70. Get the license information
71. Change the license (first call returns confirmation; confirm to proceed)
72. Get the virtualization jobs history
73. Search the virtualization jobs history for the last 7 days
74. Get the virtualization actions history
75. Search the virtualization actions history for the last 7 days
76. Get the virtualization faults history
77. Search the virtualization faults history for the last 7 days
78. Resolve or ignore the first fault from the previous result
79. Resolve all faults for the first engine
80. Resolve the first fault by its ID
81. Get the virtualization alerts history
82. Search the virtualization alerts history for the last 7 days
83. Search for all scheduled reports
84. Get the details of the first scheduled report
85. Create a scheduled report for the VDB inventory delivered weekly
86. Update that scheduled report to monthly delivery
87. Delete that scheduled report (first call returns confirmation; confirm to proceed)

**iam_tool — Account operations**
88. Search for all accounts
89. Get the details of the first account
90. Create a new account with username test-pa-user
91. Update test-pa-user's last name to Admin
92. Enable the test-pa-user account
93. Disable the test-pa-user account
94. Reset the password for test-pa-user
95. Get the tags for test-pa-user
96. Add the tag role=admin to test-pa-user
97. Remove the role=admin tag from test-pa-user
98. Get the UI profiles for test-pa-user
99. Get the current password policies
100. Update the password policy minimum length to 14

**iam_tool — Role operations**
101. Search for all roles
102. Get the details of the first role
103. Create a new role named test-pa-role
104. Update test-pa-role's description
105. Add permissions to test-pa-role
106. Remove those permissions from test-pa-role
107. Get the tags for test-pa-role
108. Add the tag level=elevated to test-pa-role
109. Remove the level=elevated tag from test-pa-role
110. Add UI profiles to test-pa-role
111. Remove those UI profiles from test-pa-role
112. Delete test-pa-role (first call returns confirmation; confirm to proceed)

**iam_tool — Access Group operations**
113. Search for all access groups
114. Get the details of the first access group
115. Create a new access group named test-pa-access-group
116. Update that access group's description to "platform admin test group"
117. Add a scope to test-pa-access-group
118. Get the first scope of that access group
119. Update that scope
120. Add object tags to that scope
121. Remove those object tags from that scope
122. Add objects to that scope
123. Remove those objects from that scope
124. Add always-allowed permissions to that scope
125. Remove those always-allowed permissions from that scope
126. Delete that scope
127. Get the tags for test-pa-access-group
128. Add the tag managed=true to test-pa-access-group
129. Remove the managed=true tag from test-pa-access-group
130. Delete test-pa-access-group (first call returns confirmation; confirm to proceed)
131. Delete test-pa-user (first call returns confirmation; confirm to proceed)

**iam_tool — API Client operations**
132. List all API clients
133. Create a new API client named test-pa-api-client
134. Delete test-pa-api-client (first call returns confirmation; confirm to proceed)

**data_connection_tool**
135. Search for all data connections
136. Get the details of the first data connection
137. Update that data connection's configuration
138. Get the tags for that data connection
139. Add the tag tier=gold to that data connection
140. Remove the tier=gold tag from that data connection

**tag_tool**
141. Search for all tags
142. Get the details of the first tag
143. Create a new tag with key classification and value internal
144. Get the usages of the classification=internal tag
145. Search the usages of the classification=internal tag
146. Delete the classification=internal tag (first call returns confirmation; confirm to proceed)

**toolkit_tool**
147. Search for all toolkits
148. Get the details of the first toolkit
149. Upload a new toolkit using a local test toolkit file
150. Get the tags for the first toolkit
151. Add the tag release=stable to that toolkit
152. Remove the release=stable tag from that toolkit
153. Delete that toolkit (first call returns confirmation; confirm to proceed)

**admin_platform_tool — AI Services**
154. List all available LLM models
155. Get the details of the first LLM model
156. Get the current AI gateway configuration
157. Update the AI gateway configuration
158. Enable AI services

**admin_platform_tool — Telemetry & Properties**
159. Get the current DCT properties
160. Update the DCT properties
161. Get the current telemetry configuration
162. Update the telemetry configuration

**admin_platform_tool — SMTP Configuration**
163. Get the current SMTP configuration
164. Update the SMTP configuration with a test SMTP server address
165. Validate the SMTP configuration

**admin_platform_tool — LDAP Configuration**
166. Get the current LDAP configuration
167. Update the LDAP configuration
168. Validate the LDAP configuration

**admin_platform_tool — SAML Configuration**
169. Get the current SAML configuration
170. Update the SAML configuration

**admin_platform_tool — Proxy Configuration**
171. Get the current proxy configuration
172. Update the proxy configuration

**vault_tool — Hashicorp Vault operations**
173. List all Hashicorp vaults
174. Search for all Hashicorp vaults
175. Get the details of the first Hashicorp vault
176. Create a new Hashicorp vault named test-pa-vault
177. Get the tags for test-pa-vault
178. Add the tag managed=true to test-pa-vault
179. Remove the managed=true tag from test-pa-vault
180. Delete test-pa-vault (first call returns confirmation; confirm to proceed)

**vault_tool — Kerberos Config operations**
181. List all Kerberos configurations
182. Search for all Kerberos configurations
183. Get the details of the first Kerberos configuration

**diagnostic_tool**
184. Check engine connectivity for the first engine
185. Check database connectivity for the first data connection
186. Check NetBackup connectivity
187. Check Commvault connectivity
188. Run a network latency test to the first engine
189. Get the network latency test result for the previous job
190. Run a DSP network test to the first engine
191. Get the DSP network test result
192. Run a network throughput test to the first engine
193. Get the network throughput test result
194. Validate file mapping by snapshot for the first VDB
195. Validate file mapping by location for the first VDB
196. Validate file mapping by timestamp for the first VDB
197. Validate file mapping from bookmark for the first VDB
