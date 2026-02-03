'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Input } from '@/components/ui';

const projectSchema = z.object({
  name: z.string().min(1, 'Project name is required'),
  site_url: z.string().url('Please enter a valid URL'),
});

export type ProjectFormData = z.infer<typeof projectSchema>;

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void | Promise<void>;
  initialData?: Partial<ProjectFormData>;
  isSubmitting?: boolean;
}

export function ProjectForm({ onSubmit, initialData, isSubmitting = false }: ProjectFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: initialData?.name ?? '',
      site_url: initialData?.site_url ?? '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <Input
        label="Project Name"
        placeholder="Enter project name"
        error={errors.name?.message}
        {...register('name')}
      />

      <Input
        label="Site URL"
        type="url"
        placeholder="https://example.com"
        error={errors.site_url?.message}
        {...register('site_url')}
      />

      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving...' : initialData ? 'Update Project' : 'Create Project'}
        </Button>
      </div>
    </form>
  );
}
