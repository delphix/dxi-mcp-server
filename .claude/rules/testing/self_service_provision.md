# Test Prompts: self_service_provision

> `DCT_TOOLSET=self_service_provision`

This toolset inherits all self_service tools. Run all 70 prompts from [self_service.md](self_service.md) first in the same thread, then continue below.

For confirmation-flow prompts, the first call returns `confirmation_required`. Follow up with "yes, go ahead and confirm" to execute.

---

**vdb_tool — provisioning actions**
71. Get the defaults for provisioning a VDB by timestamp
72. Provision a new VDB from the first dSource using those defaults, with name test-vdb-ts
73. Get the defaults for provisioning a VDB by snapshot
74. Provision a new VDB from the first available dSource snapshot using defaults, with name test-vdb-snap
75. Get the defaults for provisioning a VDB from a bookmark
76. Provision a new VDB from the first bookmark using defaults, with name test-vdb-bm
77. Get the defaults for provisioning a VDB by location
78. Provision a new VDB by location from the first dSource using defaults, with name test-vdb-loc
79. Update test-vdb-ts to rename it to test-vdb-renamed
80. Get the deletion dependencies for test-vdb-renamed
81. Switch the timeflow for test-vdb-renamed to the first available timeflow
82. Undo the last refresh on test-vdb-renamed
83. Add the tag provisioned=true to test-vdb-renamed
84. Remove the provisioned=true tag from test-vdb-renamed
85. Delete test-vdb-renamed (first call returns confirmation; confirm to proceed)

**vdb_group_tool — CRUD actions**
86. Create a new VDB group named test-group containing the first two VDBs from the earlier search
87. Get the latest snapshots for test-group
88. Provision a new VDB group from the first bookmark
89. Update test-group to rename it to test-group-renamed
90. Add the tag group=test to test-group-renamed
91. Remove the group=test tag from test-group-renamed
92. Delete test-group-renamed (first call returns confirmation; confirm to proceed)

**instance_tool**
93. Search for all CDBs
94. Get the details of the first CDB from the previous result
95. Get the tags for that CDB
96. Search for all vCDBs
97. Get the details of the first vCDB from the previous result
98. Get the tags for that vCDB

**database_template_tool**
99. Search for all database templates
100. Get the details of the first database template from the previous result
101. Create a new database template named test-template
102. Update test-template to rename it to test-template-updated
103. Get the tags for test-template-updated
104. Add the tag type=oracle to test-template-updated
105. Remove the type=oracle tag from test-template-updated
106. Delete test-template-updated (first call returns confirmation; confirm to proceed)

**hook_template_tool**
107. Search for all hook templates
108. Get the details of the first hook template from the previous result
109. Create a new hook template named test-hook with a configure clone hook type
110. Update test-hook to rename it to test-hook-updated
111. Get the tags for test-hook-updated
112. Add the tag env=staging to test-hook-updated
113. Remove the env=staging tag from test-hook-updated
114. Delete test-hook-updated (first call returns confirmation; confirm to proceed)

**virtualization_policy_tool**
115. Search for all virtualization policies
116. Get the details of the first policy from the previous result
117. Search for the targets of that policy
118. Get the tags for that policy

**environment_tool**
119. Search for all environments
120. Get the details of the first environment from the previous result
121. List the hosts in that environment
122. List the listeners in that environment
123. Get the tags for that environment

**toolkit_tool**
124. Search for all toolkits
125. Get the details of the first toolkit from the previous result

**tag_tool**
126. Search for all tags
127. Get the details of the first tag from the previous result
128. Create a new tag with key owner and value test-user
129. Delete the owner=test-user tag (first call returns confirmation; confirm to proceed)

**timeflow_tool**
130. List all timeflows
131. Search for all timeflows
132. Get the details of the first timeflow from the previous result
133. Update the name of that timeflow to test-ssp-timeflow
134. Get the snapshot day range for that timeflow
135. Repair that timeflow
136. Get the tags for that timeflow
137. Add the tag source=staging to that timeflow
138. Remove the source=staging tag from that timeflow
139. Delete that timeflow (first call returns confirmation; confirm to proceed)
