'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Input, Textarea } from '@/components/ui';
import { FileUpload, type UploadedFile } from './FileUpload';

const projectSchema = z.object({
  name: z.string().min(1, 'Project name is required'),
  site_url: z.string().url('Please enter a valid URL'),
  additional_info: z.string().optional(),
});

export type ProjectFormData = z.infer<typeof projectSchema>;

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void | Promise<void>;
  initialData?: Partial<ProjectFormData>;
  isSubmitting?: boolean;
  /** File upload props - if provided, shows file upload section */
  showFileUpload?: boolean;
  onFilesSelected?: (files: File[]) => void;
  onFileRemove?: (fileId: string) => void;
  uploadedFiles?: UploadedFile[];
  /** Custom submit button text */
  submitText?: string;
  /** Hide the submit button (for wizard flows where parent controls submission) */
  hideSubmitButton?: boolean;
  /** Form ID for external submission buttons */
  formId?: string;
}

export function ProjectForm({
  onSubmit,
  initialData,
  isSubmitting = false,
  showFileUpload = false,
  onFilesSelected,
  onFileRemove,
  uploadedFiles = [],
  submitText,
  hideSubmitButton = false,
  formId,
}: ProjectFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: initialData?.name ?? '',
      site_url: initialData?.site_url ?? '',
      additional_info: initialData?.additional_info ?? '',
    },
  });

  const defaultSubmitText = initialData ? 'Update Project' : 'Create Project';

  return (
    <form id={formId} onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <Input
        label="Project Name"
        placeholder="Enter project name"
        error={errors.name?.message}
        {...register('name')}
      />

      <Input
        label="Website URL"
        type="url"
        placeholder="https://example.com"
        error={errors.site_url?.message}
        {...register('site_url')}
      />

      {showFileUpload && (
        <div>
          <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
            Brand Documents <span className="text-warm-gray-400 font-normal">(optional)</span>
          </label>
          <FileUpload
            onFilesSelected={onFilesSelected}
            onFileRemove={onFileRemove}
            uploadedFiles={uploadedFiles}
            disabled={isSubmitting}
          />
        </div>
      )}

      <Textarea
        label="Additional Notes"
        placeholder="Any additional context about the brand, tone preferences, key competitors, etc."
        rows={4}
        {...register('additional_info')}
      />

      {!hideSubmitButton && (
        <div className="flex justify-end pt-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : submitText || defaultSubmitText}
          </Button>
        </div>
      )}
    </form>
  );
}
